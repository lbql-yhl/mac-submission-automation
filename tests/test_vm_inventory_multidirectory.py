import plistlib
import sqlite3
from pathlib import Path

import pytest

from scripts import vm_inventory
from scripts.utm_clone_macos import read_identity


def register_pool_vm(database: Path, directory: Path, name: str, suffix: int) -> Path:
    directory.mkdir(exist_ok=True)
    bundle = directory / f"{name}.utm"
    vm_inventory.reserve_vm_name(database, directory, candidate_factory=lambda: name)
    bundle.mkdir()
    (bundle / "config.plist").write_bytes(plistlib.dumps({
        "Information": {"Name": name, "UUID": f"00000000-0000-0000-0000-{suffix:012d}"},
        "Network": [{"MacAddress": f"02:00:00:00:00:{suffix:02x}"}],
        "System": {"MacPlatform": {
            "MachineIdentifier": plistlib.dumps({"ECID": suffix}),
            "HardwareModel": b"test-hardware",
        }},
    }))
    identity = read_identity(bundle / "config.plist")
    vm_inventory.register_clone(
        database, name, identity["uuid"], bundle, identity["mac"],
        identity["machine_identifier_sha256"],
    )
    vm_inventory.set_available(database, name, True)
    vm_inventory.scan_inventory(database, directory)
    return bundle


def test_single_directory_scan_preserves_rows_outside_its_scope(tmp_path: Path) -> None:
    database = tmp_path / "inventory.sqlite3"
    first, second = tmp_path / "first", tmp_path / "second"
    register_pool_vm(database, first, "abcd", 1)
    before = vm_inventory.get_record(database, "abcd")
    register_pool_vm(database, second, "efgh", 2)

    assert vm_inventory.get_record(database, "abcd") == before


def test_scan_ignores_apple_double_metadata_files(tmp_path: Path) -> None:
    database = tmp_path / "inventory.sqlite3"
    directory = tmp_path / "images"
    register_pool_vm(database, directory, "abcd", 1)
    (directory / "._abcd.utm").write_bytes(b"metadata")

    result = vm_inventory.scan_inventory(database, directory)

    assert result["directory_count"] == 1
    assert result["unregistered"] == []
    assert vm_inventory.get_record(database, "abcd")["available"] == 1


def test_multi_directory_scan_keeps_both_pools_available(tmp_path: Path) -> None:
    database = tmp_path / "inventory.sqlite3"
    first, second = tmp_path / "first", tmp_path / "second"
    register_pool_vm(database, first, "abcd", 1)
    register_pool_vm(database, second, "efgh", 2)

    result = vm_inventory.scan_inventory(database, (first, second))

    assert result["directory_count"] == 2
    assert result["newly_reusable"] == []
    for name in ("abcd", "efgh"):
        record = vm_inventory.get_record(database, name)
        assert (record["available"], record["directory_present"], record["reusable"]) == (1, 1, 0)


def test_notion_binding_scans_all_supplied_directories(tmp_path: Path) -> None:
    from scripts import utm_notion

    database = tmp_path / "inventory.sqlite3"
    first, second = tmp_path / "first", tmp_path / "second"
    register_pool_vm(database, first, "abcd", 1)
    register_pool_vm(database, second, "efgh", 2)

    assert utm_notion._bind_vm({}, "NewApp", database, (first, second), expected_vm_name="efgh") == "efgh"
    assert vm_inventory.get_record(database, "abcd")["available"] == 1


@pytest.mark.parametrize("problem", ["missing", "duplicate", "symlink"])
def test_invalid_scan_changes_no_inventory_rows(tmp_path: Path, problem: str) -> None:
    database = tmp_path / "inventory.sqlite3"
    first, second = tmp_path / "first", tmp_path / "second"
    register_pool_vm(database, first, "abcd", 1)
    if problem == "duplicate":
        second.mkdir()
        (second / "abcd.utm").mkdir()
    elif problem == "symlink":
        second.symlink_to(first, target_is_directory=True)
    before = database.read_bytes()

    with pytest.raises(vm_inventory.InventoryError):
        vm_inventory.scan_inventory(database, (first, second))

    assert database.read_bytes() == before


def test_scan_requires_explicit_recovery_for_moved_bundle(tmp_path: Path) -> None:
    database = tmp_path / "inventory.sqlite3"
    first, second = tmp_path / "first", tmp_path / "second"
    bundle = register_pool_vm(database, first, "abcd", 1)
    second.mkdir()
    bundle.rename(second / bundle.name)
    before = vm_inventory.get_record(database, "abcd")

    with pytest.raises(vm_inventory.InventoryError, match="recovery"):
        vm_inventory.scan_inventory(database, (first, second))

    assert vm_inventory.get_record(database, "abcd") == before


def test_scan_reports_bound_location_conflict_without_blocking_pool(tmp_path: Path) -> None:
    database = tmp_path / "inventory.sqlite3"
    first, second = tmp_path / "first", tmp_path / "second"
    bundle = register_pool_vm(database, first, "abcd", 1)
    register_pool_vm(database, first, "efgh", 2)
    vm_inventory.mark_used(database, "abcd", "ExistingApp")
    before = vm_inventory.get_record(database, "abcd")
    second.mkdir()
    bundle.rename(second / bundle.name)

    result = vm_inventory.scan_inventory(database, (first, second))

    assert result["location_conflicts"] == ["abcd"]
    assert vm_inventory.get_record(database, "abcd") == before
    assert vm_inventory.get_record(database, "efgh")["available"] == 1


def test_explicit_recovery_verifies_identity_and_preserves_bound_vm(tmp_path: Path) -> None:
    database = tmp_path / "inventory.sqlite3"
    first, second = tmp_path / "first", tmp_path / "second"
    bundle = register_pool_vm(database, first, "abcd", 1)
    register_pool_vm(database, first, "efgh", 2)
    vm_inventory.mark_used(database, "efgh", "ExistingApp")
    bound_before = vm_inventory.get_record(database, "efgh")
    second.mkdir()
    bundle.rename(second / bundle.name)
    vm_inventory.scan_inventory(database, first)

    restored = vm_inventory.restore_available_vms(database, (first, second), ["abcd"])

    assert restored == ["abcd"]
    record = vm_inventory.get_record(database, "abcd")
    assert record["bundle_path"] == str(second / "abcd.utm")
    assert (record["available"], record["directory_present"], record["reusable"]) == (1, 1, 0)
    assert record["application_name"] is None
    assert vm_inventory.get_record(database, "efgh")["application_name"] == bound_before["application_name"]
    before = vm_inventory.get_record(database, "efgh")
    assert vm_inventory.restore_available_vms(database, (first, second), ["abcd"]) == ["abcd"]
    assert vm_inventory.get_record(database, "efgh") == before


@pytest.mark.parametrize("problem", ["identity", "bound", "incomplete", "duplicate", "symlink"])
def test_recovery_rejects_entire_batch_on_unsafe_target(tmp_path: Path, problem: str) -> None:
    database = tmp_path / "inventory.sqlite3"
    first, second = tmp_path / "first", tmp_path / "second"
    register_pool_vm(database, first, "abcd", 1)
    bundle = register_pool_vm(database, first, "efgh", 2)
    second.mkdir()
    if problem == "identity":
        data = plistlib.loads((bundle / "config.plist").read_bytes())
        data["Network"][0]["MacAddress"] = "02:00:00:00:00:09"
        (bundle / "config.plist").write_bytes(plistlib.dumps(data))
    elif problem == "bound":
        vm_inventory.mark_used(database, "efgh", "ExistingApp")
    elif problem == "incomplete":
        with sqlite3.connect(database) as connection:
            connection.execute("UPDATE vm_inventory SET status='failed' WHERE vm_name='efgh'")
    elif problem == "duplicate":
        (second / "efgh.utm").mkdir()
    else:
        config = bundle / "config.plist"
        config.rename(bundle / "original.plist")
        config.symlink_to(bundle / "original.plist")
    before = {name: vm_inventory.get_record(database, name) for name in ("abcd", "efgh")}

    with pytest.raises(vm_inventory.InventoryError):
        vm_inventory.restore_available_vms(database, (first, second), ["abcd", "efgh"])

    assert {name: vm_inventory.get_record(database, name) for name in before} == before
