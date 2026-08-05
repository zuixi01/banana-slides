/**
 * Browser-level acceptance test for the gated Deckforge workflow.
 * AI and export endpoints are mocked; all navigation and user actions are real.
 */
import { test, expect } from '@playwright/test'

const PROJECT_ID = 'mock-project-123'
const OUTLINE_VERSION_ID = 'mock-outline-v1'
const IMAGE_TASK_ID = 'mock-image-task'
const PIXEL = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Zl1sAAAAASUVORK5CYII='

test.describe('Deckforge gated workflow (mocked AI)', () => {
  test.setTimeout(2 * 60 * 1000)

  test('idea → outline confirmation → descriptions → template → images → PPTX', async ({ page }) => {
    let outlineGenerated = false
    let outlineConfirmed = false
    let descriptionsGenerated = false
    let descriptionsConfirmed = false
    let imagesGenerated = false
    let templateStyle = ''

    const outline = [
      { title: '什么是AI', points: ['定义与核心概念'] },
      { title: 'AI的应用', points: ['行业应用案例'] },
      { title: 'AI的未来', points: ['趋势与展望'] },
    ]

    const pages = () => outline.map((item, index) => ({
      page_id: `mock-page-${index + 1}`,
      id: `mock-page-${index + 1}`,
      order_index: index,
      outline_content: item,
      description_content: descriptionsGenerated
        ? { text: `${item.title}的完整演示文稿页面描述，包含清晰的信息层级与视觉构图。` }
        : undefined,
      generated_image_url: imagesGenerated ? PIXEL : undefined,
      generated_image_path: imagesGenerated ? PIXEL : undefined,
      status: imagesGenerated
        ? 'COMPLETED'
        : descriptionsGenerated ? 'DESCRIPTION_GENERATED' : 'DRAFT',
      image_versions: imagesGenerated ? [{
        version_id: `mock-image-v${index + 1}`,
        page_id: `mock-page-${index + 1}`,
        image_path: PIXEL,
        image_url: PIXEL,
        version_number: 1,
        is_current: true,
      }] : [],
    }))

    const project = () => ({
      project_id: PROJECT_ID,
      id: PROJECT_ID,
      project_title: '人工智能基础',
      idea_prompt: '创建一份关于人工智能基础的简短PPT',
      creation_type: 'idea',
      status: imagesGenerated
        ? 'COMPLETED'
        : descriptionsConfirmed ? 'DESCRIPTIONS_CONFIRMED'
          : descriptionsGenerated ? 'DESCRIPTIONS_GENERATED'
            : outlineGenerated ? 'OUTLINE_GENERATED' : 'DRAFT',
      current_outline_version_id: outlineGenerated ? OUTLINE_VERSION_ID : null,
      confirmed_outline_version_id: outlineConfirmed ? OUTLINE_VERSION_ID : null,
      descriptions_confirmed_at: descriptionsConfirmed ? '2026-08-05T00:00:00Z' : null,
      template_mode: 'single',
      template_style: templateStyle,
      image_aspect_ratio: '16:9',
      pages: outlineGenerated ? pages() : [],
      created_at: '2026-08-05T00:00:00Z',
      updated_at: '2026-08-05T00:00:00Z',
    })

    const version = () => ({
      id: OUTLINE_VERSION_ID,
      project_id: PROJECT_ID,
      version: 1,
      status: outlineConfirmed ? 'confirmed' : 'draft',
      instruction: '根据用户需求生成初稿',
      outline: pages().map(({ id, order_index, outline_content }) => ({ id, order_index, outline_content })),
      confirmed_at: outlineConfirmed ? '2026-08-05T00:00:00Z' : null,
    })

    await page.addInitScript(() => localStorage.setItem('hasSeenHelpModal', 'true'))

    await page.route('**/api/projects', async route => {
      if (route.request().method() !== 'POST') return route.continue()
      await route.fulfill({ status: 201, json: { success: true, data: { project_id: PROJECT_ID, status: 'DRAFT' } } })
    })

    await page.route(`**/api/projects/${PROJECT_ID}`, async route => {
      const method = route.request().method()
      if (method === 'PATCH' || method === 'PUT') {
        const body = route.request().postDataJSON() as { template_style?: string }
        if (typeof body.template_style === 'string') templateStyle = body.template_style
      }
      await route.fulfill({ json: { success: true, data: project() } })
    })

    await page.route(`**/api/projects/${PROJECT_ID}/generate/outline/stream`, async route => {
      outlineGenerated = true
      const streamPages = outline.map((item, index) => ({ index, ...item }))
      const body = [
        ...streamPages.map(item => `event: page\ndata: ${JSON.stringify(item)}\n\n`),
        `event: done\ndata: ${JSON.stringify({ total: 3, pages: pages() })}\n\n`,
      ].join('')
      await route.fulfill({ status: 200, headers: { 'Content-Type': 'text/event-stream' }, body })
    })

    await page.route(`**/api/projects/${PROJECT_ID}/outline-versions`, async route => {
      await route.fulfill({ json: { success: true, data: { versions: outlineGenerated ? [version()] : [] } } })
    })
    await page.route(`**/api/projects/${PROJECT_ID}/outline-versions/${OUTLINE_VERSION_ID}/confirm`, async route => {
      outlineConfirmed = true
      await route.fulfill({ json: { success: true, data: { version: version(), message: '大纲已确认' } } })
    })
    await page.route(`**/api/projects/${PROJECT_ID}/outline-versions/snapshot`, async route => {
      await route.fulfill({ json: { success: true, data: { version: version() } } })
    })

    await page.route(`**/api/projects/${PROJECT_ID}/generate/descriptions/stream`, async route => {
      descriptionsGenerated = true
      const completePages = pages()
      const body = [
        ...completePages.map((item, index) => `event: description\ndata: ${JSON.stringify({
          page_index: index,
          page_id: item.id,
          text: item.description_content?.text,
        })}\n\n`),
        `event: done\ndata: ${JSON.stringify({ total: 3, pages: completePages })}\n\n`,
      ].join('')
      await route.fulfill({ status: 200, headers: { 'Content-Type': 'text/event-stream' }, body })
    })
    await page.route(`**/api/projects/${PROJECT_ID}/descriptions/confirm`, async route => {
      descriptionsConfirmed = true
      await route.fulfill({ json: { success: true, data: { project: project() } } })
    })

    await page.route(`**/api/projects/${PROJECT_ID}/generate/images`, async route => {
      imagesGenerated = true
      await route.fulfill({ status: 202, json: { success: true, data: { task_id: IMAGE_TASK_ID } } })
    })
    await page.route(`**/api/projects/${PROJECT_ID}/tasks/${IMAGE_TASK_ID}`, async route => {
      await route.fulfill({ json: { success: true, data: {
        task_id: IMAGE_TASK_ID, id: IMAGE_TASK_ID, status: 'COMPLETED', progress: { total: 3, completed: 3 },
      } } })
    })
    await page.route(`**/api/projects/${PROJECT_ID}/pages/*/image-versions`, async route => {
      await route.fulfill({ json: { success: true, data: { versions: [] } } })
    })

    await page.route(`**/api/projects/${PROJECT_ID}/export/pptx**`, async route => {
      await route.fulfill({ json: { success: true, data: { download_url: '/files/mock-presentation.pptx' } } })
    })
    await page.route('**/files/mock-presentation.pptx', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        body: Buffer.from('mock-pptx'),
      })
    })

    await page.goto('/')
    await expect(page).toHaveTitle(/蕉幻|Banana/i)
    await page.getByRole('button', { name: '一句话生成', exact: true }).click()
    const ideaInput = page.getByRole('textbox')
    await ideaInput.fill('创建一份关于人工智能基础的简短PPT，包含什么是AI、AI的应用和AI的未来。')
    await page.getByRole('button', { name: '下一步' }).click()

    await expect(page.getByText('什么是AI', { exact: true })).toBeVisible({ timeout: 10_000 })
    await page.getByRole('button', { name: '确认大纲' }).click()
    const next = page.getByRole('button', { name: '下一步' })
    await expect(next).toBeEnabled()
    await next.click()

    const generateDescriptions = page.getByRole('button', { name: '批量生成描述' })
    await expect(generateDescriptions).toBeVisible()
    await generateDescriptions.click()
    await expect(page.getByText('什么是AI的完整演示文稿页面描述', { exact: false })).toBeVisible({ timeout: 10_000 })
    await page.getByRole('button', { name: '前往模板配置' }).click()

    await expect(page.getByText('现代科技', { exact: true })).toBeVisible({ timeout: 10_000 })
    await page.getByText('现代科技', { exact: true }).click()
    await page.getByRole('button', { name: '应用风格' }).click()

    const generateImages = page.getByRole('button', { name: '批量生成图片 (3)' })
    await expect(generateImages).toBeEnabled()
    await generateImages.click()
    const exportButton = page.getByRole('button', { name: '导出', exact: true })
    await expect(exportButton).not.toHaveAttribute('title', /未生成图片/, { timeout: 10_000 })

    await exportButton.click()
    const exportPptx = page.getByRole('button', { name: '导出为 PPTX', exact: true })
    await expect(exportPptx).toBeEnabled()
    await exportPptx.click()
    await expect(page.getByText('PPTX 导出设置')).toBeVisible()
    const popup = page.waitForEvent('popup')
    await page.getByRole('button', { name: '开始导出' }).click()
    await expect(await popup).toHaveURL(/mock-presentation\.pptx$/)

    await page.screenshot({ path: 'test-results/e2e-mocked-final-state.png', fullPage: true })
  })
})
