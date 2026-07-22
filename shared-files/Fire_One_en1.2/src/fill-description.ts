import 'dotenv/config';
import { execSync } from 'node:child_process';
import { chmodSync, writeFileSync } from 'node:fs';

const playwright = await import('playwright');
const chromium = (playwright as any).chromium;

const APP_ID = process.env.APP_ID ?? '';
const VM_NAME = process.env.VM_NAME ?? '';
const BUNDLE_ID = process.env.BUNDLE_ID ?? '';
const DESCRIPTION = (process.env.DESCRIPTION ?? '').replace(/\\n/g, '\n');
const KEYWORDS = process.env.KEYWORDS ?? '';
const SUPPORT_URL = process.env.SUPPORT_URL ?? '';
const COPYRIGHT = process.env.COPYRIGHT ?? '';
const CONTACT_FIRST_NAME = process.env.CONTACT_FIRST_NAME ?? '';
const CONTACT_LAST_NAME = process.env.CONTACT_LAST_NAME ?? '';
const CONTACT_PHONE = process.env.CONTACT_PHONE ?? '';
const CONTACT_EMAIL = process.env.CONTACT_EMAIL ?? '';
const RELEASE_OPTION = process.env.RELEASE_OPTION ?? 'manual';
const PRIMARY_CATEGORY = process.env.PRIMARY_CATEGORY ?? '';
const PROD_SERVER_URL = process.env.PROD_SERVER_URL ?? '';
const PRIVACY_POLICY_URL = process.env.PRIVACY_POLICY_URL ?? '';
const PRIVACY_CHOICES_URL = process.env.PRIVACY_CHOICES_URL ?? '';
const CDP_ENDPOINT = process.env.CDP_ENDPOINT ?? 'http://127.0.0.1:9222';

if (!/^\d+$/.test(APP_ID)) {
  throw new Error('APP_ID 必须为纯数字');
}

if (!DESCRIPTION) {
  throw new Error('缺少 DESCRIPTION 环境变量');
}

if (!chromium) {
  throw new Error('无法加载 Playwright Chromium');
}

async function openPage(browser: any, url: string) {
  const context = browser.contexts()[0] ?? (await browser.newContext());
  const page = await context.newPage();
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  return page;
}

const THREE_MINUTES = 300000;

async function ensureChecked(locator: any) {
  if (!(await locator.isChecked())) {
    await locator.check();
  }
}

async function isFeatureVisible(locator: any) {
  return (await locator.count()) > 0 && (await locator.first().isVisible());
}

async function fillIfChanged(locator: any, desiredValue: string, label: string) {
  const currentValue = await locator.inputValue();
  const normalize = (value: string) => value.replace(/\r\n/g, '\n');

  if (normalize(currentValue) === normalize(desiredValue)) {
    console.log(`已有相同${label}，跳过填写`);
    return false;
  }

  await locator.fill(desiredValue);
  console.log(`已填写${label}`);
  return true;
}


async function clickBestSaveButton(page: any, label: string) {
  await page.waitForTimeout(500);
  const buttons = page.getByRole('button', { name: 'Save' });
  const count = await buttons.count();
  const candidates: Array<{ index: number; y: number }> = [];

  for (let index = 0; index < count; index += 1) {
    const button = buttons.nth(index);
    if (!(await button.isVisible())) {
      continue;
    }

    if (!(await button.isEnabled())) {
      continue;
    }

    const box = await button.boundingBox();
    candidates.push({ index, y: box?.y ?? Number.POSITIVE_INFINITY });
  }

  if (!candidates.length) {
    throw new Error(`找不到可点击的${label}保存按钮`);
  }

  candidates.sort((a, b) => a.y - b.y);
  await buttons.nth(candidates[0].index).click();
  console.log(`已点击${label}保存按钮`);
}

async function saveInfoPage(page: any) {
  const headingButtons = page.locator('#heading-buttons');
  if (!(await isFeatureVisible(headingButtons))) {
    console.log('未找到 Info 页面保存区域，跳过保存步骤');
    return;
  }

  const saveButton = headingButtons.getByRole('button', { name: 'Save' });
  if (!(await isFeatureVisible(saveButton))) {
    console.log('未找到 Info 页面 Save 按钮，跳过保存步骤');
    return;
  }

  if (!(await saveButton.isEnabled())) {
    console.log('Info 页面没有待保存修改，跳过 Save');
    return;
  }

  await page.waitForTimeout(500);
  await saveButton.click();
  console.log('已保存 info 页面');
}

async function fillPrivacyUrlPage(page: any) {
  const existingPrivacyUrl = page.getByText(PRIVACY_POLICY_URL, { exact: false }).first();
  if (PRIVACY_POLICY_URL && await isFeatureVisible(existingPrivacyUrl)) {
    console.log('已确认隐私政策地址相同，跳过隐私政策填写步骤');
    return;
  }

  const editButton = page.getByRole('button', { name: 'Edit', exact: true }).first();
  if (!(await isFeatureVisible(editButton))) {
    if (PRIVACY_POLICY_URL && await isFeatureVisible(existingPrivacyUrl)) {
      console.log('已确认隐私政策地址存在，跳过隐私政策填写步骤');
      return;
    }
    throw new Error('未找到隐私政策 Edit，且页面未确认已有隐私政策地址');
  }

  await editButton.click();
  console.log('已打开隐私政策弹窗');

  const privacyPolicyUrl = page.locator('#privacyPolicyUrl');
  const privacyChoicesUrl = page.locator('#privacyChoicesUrl');

  await privacyPolicyUrl.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  if (PRIVACY_POLICY_URL) {
    await fillIfChanged(privacyPolicyUrl, PRIVACY_POLICY_URL, '隐私政策网址');
  }

  await privacyChoicesUrl.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  if (PRIVACY_CHOICES_URL) {
    await fillIfChanged(privacyChoicesUrl, PRIVACY_CHOICES_URL, '用户隐私选择网址');
  }

  const dialog = page.getByRole('dialog');
  const dialogSaveButton = dialog.getByRole('button', { name: 'Save' });
  await dialogSaveButton.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  await dialogSaveButton.click();
  console.log('已保存隐私政策弹窗');
}

async function fillPrivacyDataCollectionPage(page: any) {
  const startButton = page.getByRole('button', { name: 'Get Started' });
  if (await isFeatureVisible(startButton)) {
    await startButton.click();
    console.log('已打开隐私数据收集向导');

    const collectDataYes = page.locator('#CONFIRM_COLLECT_DATA_radio_true');
    await collectDataYes.waitFor({ state: 'visible', timeout: THREE_MINUTES });
    await ensureChecked(collectDataYes);
    console.log('已选择“是，我们会从此 App 中收集数据”');

    const firstNextButton = page.getByRole('button', { name: 'Next' });
    await firstNextButton.waitFor({ state: 'visible', timeout: THREE_MINUTES });
    await firstNextButton.click();
    console.log('已点击隐私数据收集下一步');

    const deviceIdEntry = page.locator('#SELECT_CATEGORIES_checkbox_DEVICE_ID');
    await deviceIdEntry.waitFor({ state: 'visible', timeout: THREE_MINUTES });
    await ensureChecked(deviceIdEntry);
    console.log('已选择设备 ID');

    let dialog = page.getByRole('dialog');
    let saveButton = dialog.getByRole('button', { name: 'Save' });
    await saveButton.waitFor({ state: 'visible', timeout: THREE_MINUTES });
    await saveButton.click();
    console.log('已保存设备 ID 设置');

    await page.waitForTimeout(15000);
    const okButton = page.getByRole('button', { name: 'OK', exact: true });
    await okButton.waitFor({ state: 'visible', timeout: THREE_MINUTES });
    await okButton.click();
    console.log('已点击好');
    await page.waitForTimeout(15000);
    console.log('已等待 15 秒，准备继续后续保存步骤');
  } else {
    console.log('本次隐私数据收集没填写');
  }

  const deviceIdSettingsButton = page
    .locator('div.Box-sc-18eybku-0.gBWuVV')
    .filter({ hasText: 'Set Up Device ID' });
  if (await isFeatureVisible(deviceIdSettingsButton)) {
    await deviceIdSettingsButton.click();
    console.log('已打开设备 ID 详细设置弹窗');

    const thirdPartyAdvertising = page.locator('#SELECT_PURPOSES_checkbox_THIRD_PARTY_ADVERTISING');
    await thirdPartyAdvertising.waitFor({ state: 'visible', timeout: THREE_MINUTES });
    await ensureChecked(thirdPartyAdvertising);
    console.log('已勾选第三方广告');

    let dialog = page.getByRole('dialog');
    let dialogNextButton = dialog.getByRole('button', { name: 'Next' });
    await dialogNextButton.waitFor({ state: 'visible', timeout: THREE_MINUTES });
    await dialogNextButton.click();
    console.log('已点击设备 ID 设置下一步');

    const linkedFalse = page.locator('#CONFIRM_LINKING_DEVICE_ID_radioButton_false');
    await linkedFalse.waitFor({ state: 'visible', timeout: THREE_MINUTES });
    await ensureChecked(linkedFalse);
    console.log('已选择设备 ID 未与用户身份关联');

    dialog = page.getByRole('dialog');
    dialogNextButton = dialog.getByRole('button', { name: 'Next' });
    await dialogNextButton.waitFor({ state: 'visible', timeout: THREE_MINUTES });
    await dialogNextButton.click();
    console.log('已点击设备 ID 关联下一步');

    dialog = page.getByRole('dialog');
    dialogNextButton = dialog.getByRole('button', { name: 'Next' });
    await dialogNextButton.waitFor({ state: 'visible', timeout: THREE_MINUTES });
    await dialogNextButton.click();
    console.log('已继续设备 ID 追踪下一步');

    dialog = page.getByRole('dialog');
    dialogNextButton = dialog.getByRole('button', { name: 'Next' });
    await dialogNextButton.waitFor({ state: 'visible', timeout: THREE_MINUTES });
    await dialogNextButton.click();
    console.log('已再继续设备 ID 追踪下一步');

    const trackedTrue = page.locator('#CONFIRM_TRACKING_DEVICE_ID_radioButton_true');
    await trackedTrue.waitFor({ state: 'visible', timeout: THREE_MINUTES });
    await ensureChecked(trackedTrue);
    console.log('已选择设备 ID 用于追踪目的');

    dialog = page.getByRole('dialog');
    const finalSaveButton = dialog.getByRole('button', { name: 'Save' });
    await finalSaveButton.waitFor({ state: 'visible', timeout: THREE_MINUTES });
    await finalSaveButton.click();
    console.log('已保存设备 ID 设置');
  } else {
    console.log('本次设置设备 ID 没填写');
  }
}

async function publishPrivacyPage(page: any) {
  const publishedStatus = page.getByText('Published', { exact: true }).first();
  if (await isFeatureVisible(publishedStatus)) {
    console.log('privacy 已是 Published，跳过发布步骤');
    return;
  }

  const publishButton = page.getByRole('button', { name: 'Publish', exact: true }).first();
  if (!(await isFeatureVisible(publishButton))) {
    console.log('未发现 Publish，跳过 privacy 发布步骤');
    return;
  }

  await publishButton.click();
  console.log('已打开 privacy 发布弹窗');

  const dialog = page.getByRole('dialog');
  const dialogPublishButton = dialog.getByRole('button', { name: 'Publish', exact: true });
  await dialogPublishButton.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  await dialogPublishButton.click();
  console.log('已确认 privacy 发布');
}

async function waitBeforeNewPage(page: any, label: string) {
  await page.waitForTimeout(20000);
  console.log(`已等待 20 秒，准备跳转到${label}页面`);
}

async function clickSidebarItem(page: any, text: string, hrefSuffix: string) {
  const sidebar = page.getByRole('navigation', { name: 'Distribution' });
  const candidates = [
    sidebar.getByRole('link', { name: text }),
    sidebar.getByRole('menuitem', { name: text }),
    sidebar.getByText(text),
    sidebar.locator(`a[href$="${hrefSuffix}"]`),
  ];

  for (const candidate of candidates) {
    try {
      const target = candidate.first();
      await target.waitFor({ state: 'attached', timeout: 5000 });
      await target.click();
      return;
    } catch {
      continue;
    }
  }

  throw new Error(`无法找到侧边栏入口：${text}`);
}

async function openPricingPage(page: any) {
  await page.waitForTimeout(20000);
  console.log('已等待 20 秒，准备跳转到价格与销售范围页面');

  const sidebar = page.getByRole('navigation', { name: 'Distribution' });
  const candidates = [
    sidebar.getByRole('link', { name: 'Pricing and Availability' }),
    sidebar.getByRole('menuitem', { name: 'Pricing and Availability' }),
    sidebar.getByText('Pricing and Availability'),
    sidebar.locator('a[href$="/distribution/pricing"]'),
  ];

  for (const candidate of candidates) {
    try {
      const target = candidate.first();
      await target.waitFor({ state: 'attached', timeout: 5000 });
      await target.click();
      console.log('已跳转到价格与销售范围页面');
      return true;
    } catch {
      continue;
    }
  }

  console.log('本次价格与销售范围没填写');
  return false;
}

async function fillPricingPage(page: any) {
  const addPricingButton = page.getByRole('button', { name: 'Add Pricing', exact: true }).first();
  if (!(await isFeatureVisible(addPricingButton))) {
    console.log('未发现 Add Pricing，跳过定价步骤');
    return;
  }

  await addPricingButton.click();
  console.log('已打开添加定价弹窗');

  const priceButton = page.locator('#basePricePointId');
  await priceButton.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  await priceButton.click();
  console.log('已打开价格选取器');

  const zeroPriceOption = page.getByRole('button', { name: '$0.00' });
  await zeroPriceOption.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  await zeroPriceOption.click();
  console.log('已选择 0 元');

  let dialog = page.getByRole('dialog');
  let nextButton = dialog.getByRole('button', { name: 'Next' });
  await nextButton.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  await nextButton.click();
  console.log('已点击定价下一步');

  dialog = page.getByRole('dialog');
  nextButton = dialog.getByRole('button', { name: 'Next' });
  await nextButton.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  await nextButton.click();
  console.log('已继续定价下一步');

  dialog = page.getByRole('dialog');
  const confirmButton = dialog.getByRole('button', { name: 'Confirm' });
  await confirmButton.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  await confirmButton.click();
  console.log('已确认定价，等待十五秒');
  await page.waitForTimeout(15000);
}

async function fillPricingAvailabilityPage(page: any) {
  const setAvailabilityButton = page.getByText('Set Up Availability', { exact: true }).first();
  if (!(await isFeatureVisible(setAvailabilityButton))) {
    console.log('未发现 Set Up Availability，跳过供应范围步骤');
    return;
  }

  await setAvailabilityButton.click();
  console.log('已打开供应情况弹窗');

  let dialog = page.getByRole('dialog');
  const granularRadio = dialog.locator('#SETUP_GRANULAR');
  await granularRadio.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  await ensureChecked(granularRadio);
  console.log('已选择特定国家或地区');

  let nextButton = dialog.getByRole('button', { name: 'Next' });
  await nextButton.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  await nextButton.click();
  console.log('已进入国家或地区选择步骤');

  const selectAllButton = page.getByRole('button', { name: 'All' });
  await selectAllButton.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  await selectAllButton.click();
  console.log('已点击选择全部');

  for (const countryId of ['TWN', 'CHN', 'MAC', 'HKG']) {
    const checkbox = page.locator(`#${countryId}`);
    if (await isFeatureVisible(checkbox)) {
      if (await checkbox.isChecked()) {
        await checkbox.uncheck();
        console.log(`已取消勾选${countryId}`);
      }
    }
  }

  dialog = page.getByRole('dialog');
  const confirmNextButton = dialog.getByRole('button', { name: 'Next' });
  await confirmNextButton.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  await confirmNextButton.click();
  console.log('已进入供应情况确认步骤');

  dialog = page.getByRole('dialog');
  const confirmButton = dialog.getByRole('button', { name: 'Confirm' });
  await confirmButton.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  await confirmButton.click();
  console.log('已确认供应情况');
}

async function fillInfoPage(page: any) {
  if (!PRIMARY_CATEGORY) {
    console.log('本次设置内容版权没填写');
    console.log('本次设置年龄分级没填写');
    console.log('本次设置生产环境服务器URL没填写');
    return;
  }

  await setPrimaryCategory(page);
  await page.waitForTimeout(3000);
  await setAgeRating(page);
  await page.waitForTimeout(3000);

  const contentRightsButton = page.getByRole('button', { name: 'Set Up Content Rights Information' });
  if (await isFeatureVisible(contentRightsButton)) {
    await contentRightsButton.click();
    console.log('已打开内容版权弹窗');
    await page.waitForTimeout(3000);

    const contentRightsNo = page.locator('#DOES_NOT_USE_THIRD_PARTY_CONTENT');
    if (await isFeatureVisible(contentRightsNo)) {
      await ensureChecked(contentRightsNo);
      console.log('已选择“内容版权：不，它不包含、显示或访问第三方内容”');
    } else {
      console.log('未找到内容版权选项，跳过勾选');
    }

    const dialog = page.getByRole('dialog');
    const doneButton = dialog.getByRole('button', { name: 'Done' });
    if (await isFeatureVisible(doneButton)) {
      await doneButton.first().click();
      await page.waitForTimeout(3000);
      await dialog.waitFor({ state: 'hidden', timeout: THREE_MINUTES });
      console.log('已确认内容版权弹窗');
    }
  } else {
    console.log('本次设置内容版权没填写');
  }

  if (PROD_SERVER_URL) {
    const sections = page.locator('section, div, li, td').filter({ has: page.getByText('Production Server URL', { exact: true }) });
    const sectionCount = await sections.count();
    let clicked = false;

    for (let index = 0; index < sectionCount; index += 1) {
      const section = sections.nth(index);
      const prodUrlButton = section.getByRole('button', { name: 'Set Up URL' });

      if (!(await isFeatureVisible(prodUrlButton))) {
        continue;
      }

      const sectionBox = await section.boundingBox();
      const buttonBox = await prodUrlButton.first().boundingBox();
      if (!sectionBox || !buttonBox) {
        continue;
      }

      const isLeftSideSection = buttonBox.x < sectionBox.x + sectionBox.width / 2;
      if (!isLeftSideSection) {
        continue;
      }

      await prodUrlButton.first().click();
      clicked = true;
      console.log('已打开生产环境服务器 URL 输入框');
      await page.waitForTimeout(3000);

      const serverUrlInput = page.locator('#subscriptionStatusUrl');
      await serverUrlInput.waitFor({ state: 'visible', timeout: THREE_MINUTES });
      await serverUrlInput.fill(PROD_SERVER_URL);
      console.log('已填写生产环境服务器 URL');
      await page.waitForTimeout(3000);

      const prodUrlDialog = page.getByRole('dialog');
      const prodUrlDialogSave = prodUrlDialog.getByRole('button', { name: 'Save' });
      await prodUrlDialogSave.waitFor({ state: 'visible', timeout: THREE_MINUTES });
      await prodUrlDialogSave.click();
      console.log('已确认生产环境服务器 URL 弹窗');
      await page.waitForTimeout(3000);
      break;
    }

    if (!clicked) {
      console.log('未找到 Production Server URL 的 Set Up URL 按钮');
    }
  } else {
    console.log('本次设置生产环境服务器URL没填写');
  }

  await page.waitForTimeout(3000);
  await saveInfoPage(page);
}

async function fillDescriptionPage(page: any) {
  const description = page.getByLabel('Description');
  const keywords = page.getByLabel('Keywords');
  const supportUrl = page.getByLabel('Support URL');
  const copyright = page.getByLabel('Copyright');
  const contactFirstName = page.getByLabel('First name');
  const contactLastName = page.getByLabel('Last name');
  const contactPhone = page.getByLabel('Phone number');
  const contactEmail = page.getByLabel('Email');
  const demoAccountRequired = page.getByLabel('Sign-in required');
  const manualRelease = page.getByLabel('Manually release this version');

  await description.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  await keywords.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  await supportUrl.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  await copyright.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  await contactFirstName.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  await contactLastName.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  await contactPhone.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  await contactEmail.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  await demoAccountRequired.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  await manualRelease.waitFor({ state: 'visible', timeout: THREE_MINUTES });

  await fillIfChanged(description, DESCRIPTION, '描述');

  if (KEYWORDS) {
    await fillIfChanged(keywords, KEYWORDS, '关键词');
  }

  if (SUPPORT_URL) {
    await fillIfChanged(supportUrl, SUPPORT_URL, '技术支持网址');
  }

  if (COPYRIGHT) {
    await fillIfChanged(copyright, COPYRIGHT, '版权');
  }

  if (CONTACT_FIRST_NAME) {
    await fillIfChanged(contactFirstName, CONTACT_FIRST_NAME, '联系名字');
  }

  if (CONTACT_LAST_NAME) {
    await fillIfChanged(contactLastName, CONTACT_LAST_NAME, '联系姓氏');
  }

  if (CONTACT_PHONE) {
    await fillIfChanged(contactPhone, CONTACT_PHONE, '联系电话');
  }

  if (CONTACT_EMAIL) {
    await fillIfChanged(contactEmail, CONTACT_EMAIL, '联系邮箱');
  }

  if (await demoAccountRequired.isChecked()) {
    await demoAccountRequired.uncheck();
    console.log('已取消“需要登录”勾选');
  }

  if (RELEASE_OPTION === 'manual') {
    await ensureChecked(manualRelease);
    console.log('已选择“手动发布此版本”');
  }

}

async function setPrimaryCategory(page: any) {
  const primaryCategorySelect = page.locator('select[name="primaryCategory"]');
  await primaryCategorySelect.waitFor({ state: 'visible', timeout: THREE_MINUTES });

  if ((await primaryCategorySelect.inputValue()) === PRIMARY_CATEGORY) {
    console.log(`已有相同主要分类：${PRIMARY_CATEGORY}，跳过填写`);
    return;
  }

  await primaryCategorySelect.selectOption({ value: PRIMARY_CATEGORY });
  console.log(`已选择主要分类：${PRIMARY_CATEGORY}`);
}

async function setAgeRating(page: any) {
  const openButton = page.getByRole('button', { name: 'Set Up Age Ratings' });
  if (!(await isFeatureVisible(openButton))) {
    console.log('本次设置年龄分级没填写');
    return;
  }

  await openButton.click();
  console.log('已打开年龄分级弹窗');

  const steps = [
    [
      '#parentalControls__false',
      '#ageAssurance__false',
      '#unrestrictedWebAccess__false',
      '#userGeneratedContent__false',
      '#messagingAndChat__false',
      '#advertising__false',
      '#socialMedia__false',
      '#socialMediaAgeRestricted__false'
    ],
    [
      '#profanityOrCrudeHumor__NONE',
      '#horrorOrFearThemes__NONE',
      '#alcoholTobaccoOrDrugUseOrReferences__NONE'
    ],
    [
      '#medicalOrTreatmentInformation__NONE',
      '#healthOrWellnessTopics__false'
    ],
    [
      '#matureOrSuggestiveThemes__NONE',
      '#sexualContentOrNudity__NONE',
      '#sexualContentGraphicAndNudity__NONE'
    ],
    [
      '#violenceCartoonOrFantasy__NONE',
      '#violenceRealistic__NONE',
      '#violenceRealisticProlongedGraphicOrSadistic__NONE',
      '#gunsOrOtherWeapons__NONE'
    ],
    [
      '#gamblingSimulated__NONE',
      '#contests__NONE',
      '#gambling__false',
      '#lootBox__false'
    ]
  ];

  for (const step of steps) {
    for (const selector of step) {
      const input = page.locator(selector);
      if (!(await isFeatureVisible(input))) {
        console.log('本次设置年龄分级没填写');
        return;
      }
      await ensureChecked(input);
    }
    const nextButton = page.getByRole('button', { name: 'Next' });
    if (!(await isFeatureVisible(nextButton))) {
      console.log('本次设置年龄分级没填写');
      return;
    }
    await nextButton.click();
    console.log('已点击年龄分级下一步');
  }

  const overrideToHigherAge = page.locator('label:has-text("Override to Higher Age Rating") input[type="radio"]');
  if (!(await isFeatureVisible(overrideToHigherAge))) {
    console.log('本次设置年龄分级没填写');
    return;
  }
  await ensureChecked(overrideToHigherAge);
  console.log('已选择年龄类别和覆盖：覆盖至更高的年龄分级');

  const ratingSelect = page.locator('select[name="ageRatingOverride"]');
  if (await isFeatureVisible(ratingSelect)) {
    await ratingSelect.selectOption({ value: 'EIGHTEEN_PLUS' });
    console.log('已选择年龄分级：18 岁以上');
  } else {
    console.log('本次设置年龄分级没填写');
    return;
  }

  const dialog = page.getByRole('dialog');
  const dialogSaveButton = dialog.getByRole('button', { name: 'Save' });
  if (await isFeatureVisible(dialogSaveButton)) {
    await dialogSaveButton.click();
    console.log('已保存年龄分级');
  } else {
    console.log('本次设置年龄分级没填写');
  }
}

void fillInfoPage;

async function fillIntegrationsPage(page: any) {
  const integrationsRoot = page.locator('#integrations');
  await integrationsRoot.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  console.log('已检测到 integrations 页面元素');

  await page.waitForTimeout(30000);
  console.log('已等待 30 秒，准备检查请求访问');

  const requestAccessButton = page.getByRole('button', { name: 'Request Access' });
  if (await isFeatureVisible(requestAccessButton)) {
    await requestAccessButton.click();
    console.log('已打开请求访问弹窗');

    const acceptCheckbox = page.locator('input[name="accept"]');
    await acceptCheckbox.waitFor({ state: 'visible', timeout: THREE_MINUTES });
    await ensureChecked(acceptCheckbox);
    console.log('已勾选 accept');

    const submitButton = page.getByRole('button', { name: 'Submit' });
    await submitButton.waitFor({ state: 'visible', timeout: THREE_MINUTES });
    await submitButton.click();
    console.log('已提交请求访问');
  } else {
    console.log('本次请求访问没填写');
  }

  const generateApiKeyButton = page.getByRole('button', { name: 'Generate API Key' });
  await generateApiKeyButton.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  await generateApiKeyButton.click();
  console.log('已打开生成 API 密钥弹窗');

  await page.waitForTimeout(10000);
  console.log('已等待 10 秒，准备填写名称');

  const nameInput = page.locator('#name');
  await nameInput.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  await nameInput.fill(COPYRIGHT);
  console.log('已填写名称');

  const rolesInput = page.locator('#roles input[name="roles"]');
  await rolesInput.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  await rolesInput.click();
  console.log('已打开选择职能弹框');

  const managementRole = page.getByRole('button', { name: 'Admin', exact: true });
  await managementRole.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  await managementRole.click();
  console.log('已选择管理职能');

  const generateButton = page.getByRole('dialog').getByRole('button', { name: 'Generate', exact: true });
  await generateButton.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  await generateButton.click();
  console.log('已生成 API 密钥');

  const issuerLabel = page.getByText('Issuer ID');
  await issuerLabel.waitFor({ state: 'visible', timeout: THREE_MINUTES });

  const issuerValue = page.locator('span[role="presentation"]').first();
  await issuerValue.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  const issuer = ((await issuerValue.textContent()) ?? '').trim();
  console.log('Issuer ID 已读取');

  const keyIdButton = page.getByRole('button', { name: 'Copy Key ID' }).first();
  await keyIdButton.waitFor({ state: 'visible', timeout: THREE_MINUTES });

  const keyIdValue = page.locator('p').filter({ hasText: /^[A-Z0-9]+$/ }).first();
  await keyIdValue.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  const key = ((await keyIdValue.textContent()) ?? '').trim();
  console.log('Key ID 已读取');

  const downloadButton = page.getByRole('button', { name: 'Download' });
  await downloadButton.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  await downloadButton.click();
  console.log('已打开下载弹窗');

  const downloadDialog = page.getByRole('dialog');
  const dialogDownloadButton = downloadDialog.getByRole('button', { name: 'Download' });
  await dialogDownloadButton.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  const downloadPromise = page.waitForEvent('download');
  await dialogDownloadButton.click();
  const download = await downloadPromise;
  const p8FileName = download.suggestedFilename();
  const downloadPath = `${process.env.HOME}/Downloads/${p8FileName}`;
  await download.saveAs(downloadPath);
  console.log('P8 私钥已下载并安全保存');
  console.log('已确认下载');

  return { issuer, key, p8FileName };
}

async function fillEnrollmentPage(page: any) {
  const acceptedYes = page.locator('input[name="paidAppsAgreement"][value="yes"]');
  await acceptedYes.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  await ensureChecked(acceptedYes);
  console.log('已选择接受条款');

  await page.waitForTimeout(15000);
  console.log('已等待 15 秒，准备填写 Associated Developer Accounts');

  const noSelectors = [
    'input[name="youMajorityPartnership"][value="no"]',
    'input[name="anotherMajorityPartnership"][value="no"]',
    'input[name="youUltimateDecisionMaking"][value="no"]',
    'input[name="anotherUltimateDecisionMaking"][value="no"]',
  ];

  for (const selector of noSelectors) {
    const input = page.locator(selector);
    await input.waitFor({ state: 'visible', timeout: THREE_MINUTES });
    await ensureChecked(input);
  }
  console.log('已勾选 Associated Developer Accounts 的所有 No');

  const policyAgree = page.locator('input[name="chkPolicyAgree"]');
  await policyAgree.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  await ensureChecked(policyAgree);
  console.log('已勾选协议确认');

  const submitButton = page.locator('#submit');
  await submitButton.waitFor({ state: 'visible', timeout: THREE_MINUTES });
  await submitButton.click();
  console.log('已提交 enrollment 表单');
}

async function runPostPricingAutomation(params: { issuer: string; key: string; p8FileName: string; }) {
  if (!VM_NAME) {
    throw new Error('缺少 VM_NAME 环境变量');
  }
  if (!BUNDLE_ID) {
    throw new Error('缺少 BUNDLE_ID 环境变量');
  }

  const { issuer, key, p8FileName } = params;
  const baseDir = `/Users/${VM_NAME}/Downloads/apple-store-bm`;
  const xlsxName = `${COPYRIGHT}.xlsx`;
  const pngName = `${COPYRIGHT}.png`;
  const configDir = `${baseDir}/config`;
  const keyFileMatch = /^AuthKey_([A-Z0-9]{10})\.p8$/.exec(p8FileName);

  if (!keyFileMatch) {
    throw new Error(`下载的 API 私钥文件名格式无效：${p8FileName}`);
  }

  const downloadedKeyId = keyFileMatch[1];
  if (downloadedKeyId !== key) {
    throw new Error('下载的 API 私钥文件与当前 Key ID 不匹配');
  }

  execSync(`mv \"$HOME/Downloads/${xlsxName}\" \"${baseDir}/\"`, { stdio: 'inherit' });
  execSync(`mkdir -p \"${baseDir}/cache/12345\"`, { stdio: 'inherit' });
  execSync(`mv \"$HOME/Downloads/${pngName}\" \"${baseDir}/cache/12345/\"`, { stdio: 'inherit' });
  execSync(`mkdir -p \"${configDir}\"`, { stdio: 'inherit' });
  execSync(`mv \"$HOME/Downloads/${p8FileName}\" \"${configDir}/\"`, { stdio: 'inherit' });

  const prodConfigPath = `${configDir}/prod.yml`;
  const prodConfig = `apple_store:
  issuer_id: ${issuer}
  key_id: ${key}
  private_key_path: ./config/${p8FileName}

app_info:
  bundle_id: ${BUNDLE_ID}
  platform: IOS
  version: 1.0
  locale: en-US
  preview_type: IPHONE_67
  update_version_txt: test version
  file_path:
  dir_path:
`;
  writeFileSync(prodConfigPath, prodConfig, { encoding: 'utf8' });
  chmodSync(prodConfigPath, 0o600);
  chmodSync(`${configDir}/${p8FileName}`, 0o600);

  execSync(
    `test -f \"${configDir}/${p8FileName}\" && \
     grep -Fqx 'key_id: ${key}' \"${prodConfigPath}\" && \
     grep -Fqx 'private_key_path: ./config/${p8FileName}' \"${prodConfigPath}\" && \
     grep -Fqx 'bundle_id: ${BUNDLE_ID}' \"${prodConfigPath}\"`,
    { stdio: 'inherit' }
  );

  const toolPath = `${baseDir}/apple_store_tools`;
  execSync(
    `test -f \"${toolPath}\" && \
     xattr -d com.apple.quarantine \"${toolPath}\" 2>/dev/null || true; \
     chmod 755 \"${toolPath}\"; \
     test -x \"${toolPath}\"; \
     if xattr -p com.apple.quarantine \"${toolPath}\" >/dev/null 2>&1; then \
       echo 'apple_store_tools quarantine 属性仍存在' >&2; \
       exit 126; \
     fi`,
    { stdio: 'inherit' }
  );

  execSync(`cd \"${baseDir}\" && ./apple_store_tools iap-enhanced \"./${xlsxName}\" 12345`, { stdio: 'inherit' });
}

async function main() {
  const browser = await chromium.connectOverCDP(CDP_ENDPOINT);
  const enrollmentUrl = 'https://developer.apple.com/app-store/small-business-program/enroll/';
  const integrationsUrl = 'https://appstoreconnect.apple.com/access/integrations';
  const inflightUrl = `https://appstoreconnect.apple.com/apps/${APP_ID}/distribution/ios/version/inflight`;

  const enrollmentPage = await openPage(browser, enrollmentUrl);
  await enrollmentPage.waitForLoadState('domcontentloaded', { timeout: THREE_MINUTES });
  console.log('已打开 enrollment 页面');
  await fillEnrollmentPage(enrollmentPage);

  const integrationsPage = await openPage(browser, integrationsUrl);
  await integrationsPage.waitForLoadState('domcontentloaded', { timeout: THREE_MINUTES });
  console.log('已打开 integrations 页面');
  const integrationData = await fillIntegrationsPage(integrationsPage);

  const page = await openPage(browser, inflightUrl);
  await fillDescriptionPage(page);

  await clickBestSaveButton(page, 'inflight 页面');

  await page.waitForTimeout(30000);
  console.log('已等待 30 秒，准备跳转到 App 信息页面');

  await clickSidebarItem(page, 'App Information', '/distribution/info');
  console.log('已跳转到 App 信息页面');

  await page.waitForLoadState('domcontentloaded', { timeout: THREE_MINUTES });
  await waitBeforeNewPage(page, 'App 信息');
  await fillInfoPage(page);

  await page.waitForTimeout(30000);
  console.log('已等待 30 秒，准备跳转到 App 隐私页面');

  await clickSidebarItem(page, 'App Privacy', '/distribution/privacy');
  console.log('已跳转到 App 隐私页面');

  await page.waitForLoadState('domcontentloaded', { timeout: THREE_MINUTES });
  await waitBeforeNewPage(page, 'App 隐私');
  await fillPrivacyUrlPage(page);
  await page.waitForTimeout(45000);
  console.log('已等待 45 秒，准备点击开始进行隐私数据收集向导');
  await fillPrivacyDataCollectionPage(page);
  await publishPrivacyPage(page);

  const pricingOpened = await openPricingPage(page);
  if (pricingOpened) {
    await page.waitForLoadState('domcontentloaded', { timeout: THREE_MINUTES });
    await waitBeforeNewPage(page, 'Pricing and Availability');
    await fillPricingPage(page);
  }
  await fillPricingAvailabilityPage(page);
  await runPostPricingAutomation(integrationData);

  await page.waitForTimeout(1000);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
