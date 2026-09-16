# 工作台界面设计

定位是供业务分析人员持续使用的分析仪表台，不是产品宣传页。视觉层级优先展示当前数据集、分析过程和可核对的图表；未生成结果时只显示明确的空状态，不用虚构数据装饰页面。

- 导航使用深蓝灰，主工作区使用冷白与浅灰；蓝色代表操作，青绿色代表成功，琥珀色代表需注意的信息。
- 颜色、间距、圆角及按钮/面板语义集中在 `frontend/app/globals.css` 的 token 区域。组件不单独发明一套颜色体系。
- 桌面端保持对话和数据/图表双栏；窄屏按“数据集 → 对话 → 图表”顺序排列。连接设置在窄屏顶部仍可进入。
- 空状态说明下一步；图表占位网格不携带任何数据值。键盘焦点、减少动态效果、表单标签和弹窗焦点循环有对应样式与测试。

方法参考：[Anthropic frontend-design](https://github.com/anthropics/skills/tree/main/skills/frontend-design)、[Vercel web-design-guidelines](https://github.com/vercel-labs/agent-skills/tree/main/skills/web-design-guidelines)、[UI UX Pro Max design-system](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill/tree/main/.claude/skills/design-system)。仅参考设计流程与检查原则，没有引入第三方运行时代码或素材。
