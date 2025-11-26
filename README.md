## 传话筒（astrbot_plugin_chuanhuatong）

> **当前版本：v1.6.0**

将 AstrBot 的纯文本回复转换成带立绘的 GalGame 风聊天框图片，支持情绪差分、多层文本、拖拽式 WebUI 布局与自定义组件模板。

<img width="511" height="684" alt="image" src="https://github.com/user-attachments/assets/f84f4295-02fc-430b-b390-fb23758bdd77" />


---

## 使用场景

- **聊天对话美化**：所有回复统一渲染为带立绘的对话框图片，适合直播、录播、截图分享等场景。
- **多情绪立绘**：通过在文本中插入 `&happy&` / `&sad&` 等标签，自动切换对应情绪立绘。
- **自定义 UI 布局**：在 WebUI 中拖拽主文本框、角色立绘、多个文本 / 图片 / 毛玻璃层，做成自己的聊天框模板。

---

## 主要特性

- **统一图片渲染**
  - 拦截 Bot 输出的文本，在发送前统一转为图片，渲染失败自动降级为原始文本。
  - 支持渲染字符阈值：过长文本自动退回纯文本，避免生成大图。

- **自动背景 / 立绘管理**
  - 自动从 `background/`、`renwulihui/<情绪>/` 等目录中随机抽取素材。
  - 支持 `__auto__` / `__random__` 模式，也可以在 WebUI 中指定固定立绘。

- **情绪标签驱动立绘**
  - 在回答中插入 `&happy&`、`&shy&`、`&angry&` 等标签即可切换对应情绪立绘。
  - 情绪集合、对应子目录、颜色等由 `_conf_schema.json` 的 `emotion_sets` 统一管理。

- **拖拽式 WebUI 布局编辑器**
  - 所见即所得编辑画布：可拖拽 / 缩放主文本框、角色立绘、文本层、图片组件、毛玻璃层。
  - 图层列表类似 Photoshop：支持调整 z-index、透明度、可见性、删除等。
  - 文本层支持自定义字体、字号、颜色、**描边宽度 / 颜色**，边框可拖拽控制自动换行与字体自适应。

- **多预设保存 / 一键切换**
  - WebUI 保存时可输入名称，自动写入 `data/.../presets/*.json`，方便管理不同剧本皮肤。
  - 在任何对话中发送 `/切换预设 预设名`（兼容 `*切换预设` 写法），即可即时切换到指定布局，无需离开聊天窗口。
  - 预设管理面板内置“覆盖当前”“另存为”按钮，实时刷新角色组与立绘预览，所见即所得。

- **立绘角色分组 + 差分**
  - WebUI 上传立绘前，可先选择“角色分组”，再选择情绪/差分目录，或分别填写自定义名称。
  - 插件会自动落盘到 `data/.../characters/<角色>/<情绪>/`，预设中可指定某个角色组，渲染时会根据情绪标签自动切换该角色组下的对应差分。

- **组件与毛玻璃模板**
  - 可以将对话框外框、按钮、角标等作为“组件图层”自由摆放。
  - 毛玻璃效果作为独立图层存在，可与主文本框分离，放在任意位置。

- **本地 Pillow 渲染**
  - 完全基于本地 Pillow 渲染，无需浏览器 / Playwright。
  - 如渲染出错会自动回退为纯文本发送，保证消息不丢失。

<img width="2111" height="1111" alt="image" src="https://github.com/user-attachments/assets/6fc31c10-8c61-480c-93ac-f4b09c4306cc" />


---

## 安装与启用

1. **复制插件目录**
   - 将整个 `astrbot_plugin_chuanhuatong` 目录放入：
     - `AstrBot/data/plugins/astrbot_plugin_chuanhuatong`

2. **在 AstrBot 中启用插件**
   - 打开 AstrBot WebUI → **插件管理**，启用 `传话筒（astrbot_plugin_chuanhuatong）`。
   - 如有需要，可先点击“配置”按钮预设端口、情绪标签、渲染阈值等。

3. **确认 WebUI 端口**
   - 默认 WebUI 监听：`http://127.0.0.1:18765`
   - 可在配置中修改 `webui_host` / `webui_port`，请确保端口未被其他程序占用。
<img width="947" height="185" alt="image" src="https://github.com/user-attachments/assets/9318fc9c-cdab-476c-9a1b-4eb2212a5409" />


---

## WebUI 布局编辑器

- **访问方式**
  - 浏览器打开：`http://127.0.0.1:18765?token=你的webui_token`
  - 或在请求头中携带：`Authorization: Bearer <token>`

- **画布与图层**
  - 可在画布中直接拖拽 / 缩放以下元素：
    - 主文本框（对白文本）
    - 角色立绘框
    - 文本图层（标题、副标题、角标文字等）
    - 图片组件（装饰框、按钮、图标等）
    - 毛玻璃层
  - 图层列表类似 PS：
    - 支持选中图层、调整顺序（z-index）、隐藏 / 显示、删除。

- **文本与字体**
  - 文本层支持：
    - 自定义字体（系统字体 + 上传字体）
    - 字号、行高、对齐方式
    - 字体颜色、描边宽度、描边颜色
  - 主文本框及文本层均支持自动换行与字体自适应缩放，使文本完整落在框内。

- **资产上传**
  - WebUI 提供卡片式“上传资产”区域：
    - 上传 PNG/WebP/GIF 到组件目录。
    - 上传 TTF/TTC/OTF 字体到字体目录。
    - 上传 PNG/WebP 立绘到 `data/.../characters/<角色>/<情绪>/`，上传前可选择角色分组与情绪（或自定义目录），方便与自动情绪匹配。
  - 上传成功后，组件 / 字体 / 立绘会自动出现在下拉列表中可选。

- **配置持久化**
  - 布局配置保存在：
    - `AstrBot/data/plugin_data/astrbot_plugin_chuanhuatong/layout_state.json`
  - 重启 AstrBot 或重新加载插件不会丢失布局；点击“重置布局”可回到插件内置的默认模板。

<img width="343" height="414" alt="image" src="https://github.com/user-attachments/assets/1223e0a0-daf0-43ee-bbc2-86a2faf34599" />


---

## 快速预设指令

- **切换指令**：在任意对话中发送 `/切换预设 预设名称`（亦可写成 `*切换预设`），插件会立即加载对应的 `presets/*.json` 并同步 WebUI 当前布局。
- **命名约定**：名称与 WebUI 保存弹窗中填写的一致，不区分大小写；找不到同名预设时会提示失败。
- **典型用法**：为不同人物/舞台准备多套布局，直播中直接通过文字指令切换，无需离开聊天窗口。

---

## 情绪标签与立绘规则

- **标签写法**
  - 在模型回答中插入形如 `&happy&` 的标记，例如：
    - `今天的我可是超开心的呢！&happy&`
  - 插件会解析这些标签，映射到对应的情绪 key，并选择对应情绪文件夹下的一张立绘图。

- **默认标签集合**
  - 典型内置标签（示例）：
    - `&happy&` / `&sad&` / `&shy&` / `&surprise&` / `&angry&` / `&neutral&` 等
  - 具体可用标签及对应文件夹请以 `_conf_schema.json` 中的 `emotion_sets` 为准。

- **自动提示与手动标签**
  - `enable_emotion_prompt = true` 时，插件会在发给 LLM 的提示中追加说明，请模型在文本中插入情绪标签。
  - 也可以关闭自动提示，在其他插件 / Prompt 中自行控制标签写法。

- **默认情绪与回退逻辑**
  - 如果文本中没有出现任何已知标签，则使用配置项 `default_emotion`。
  - 若 `default_emotion` 无法匹配到有效目录，会使用第一个已启用的情绪作为回退。

<img width="427" height="509" alt="image" src="https://github.com/user-attachments/assets/c11e5cfa-3e53-4d89-af7a-208648effa1f" />


---

## 资源目录结构

**插件目录（静态资源）**

```text
astrbot_plugin_chuanhuatong/
├── background/          # 背景图（png/jpg/webp），随机抽取
├── renwulihui/          # 立绘根目录，按情绪或自定义子文件夹分类
└── zujian/              # 内置组件（模板框、装饰按钮等 PNG/WebP/GIF）
```

- **背景图**
  - 放在 `background/` 下，支持 png/jpg/webp。
  - 渲染时会随机选取一张，也可以在 WebUI 中指定固定背景。

- **立绘**
  - 建议使用带透明通道的 PNG。
  - 可以自由创建子目录，例如：
    - `renwulihui/happy/…`
    - `renwulihui/sad/…`
  - 在 `emotion_sets` 中将情绪 key 映射到对应的子目录，即可按情绪抽取立绘。

- **内置组件模板**
  - 建议将以下模板图片放入 `zujian/` 目录，例如：
    - `名称框.png`、`底框.png`、`线索.png`、`设置.png` 等。
  - 完整路径示例：
    - `AstrBot/data/plugins/astrbot_plugin_chuanhuatong/zujian/名称框.png`
  - 这样默认布局中的组件图层就能直接引用这些图片，第一次打开 WebUI 即可看到完整模板布局。

---

## 数据与用户上传目录

**运行时数据目录（自动创建）**

```text
AstrBot/data/plugin_data/astrbot_plugin_chuanhuatong/
├── layout_state.json   # WebUI 保存的布局（用户可编辑）
├── presets/            # 多预设 JSON，每个文件对应一个布局
├── zujian/             # WebUI 上传的额外组件（PNG/WebP/GIF）
├── characters/         # WebUI 上传的立绘，支持 <角色>/<情绪>/ 文件夹结构
└── fonts/              # WebUI 上传的字体文件
```

- 默认情况下，路径位于 `AstrBot/data/plugin_data/astrbot_plugin_chuanhuatong/`；若 AstrBot 被配置为使用其他数据根目录，插件会在日志中输出实际路径，可据此定位文件。
- 立绘目录推荐结构：`characters/<角色名>/<情绪名>/<文件>`，例如 `characters/白毛/happy/001.png`。
- 直接将组件 / 立绘 / 字体文件放入上述目录（及其子目录）也会被 WebUI 识别。
- 用户上传的组件与字体会与插件内置的文件一起出现在下拉列表中，可在 WebUI 中统一管理。

<img width="653" height="194" alt="image" src="https://github.com/user-attachments/assets/c0ae569b-c8b6-49f0-9047-1913b1a420f9" />


---

### 立绘角色分组

- **目录层级**：推荐结构为 `characters/<角色>/<情绪>/<文件>`，角色名和情绪名均可自定义；也兼容旧版的 `characters/<情绪>/<文件>` 单层结构。
- **上传流程**：在 WebUI 的“资源上传”面板中，先选择或输入角色分组，再选择情绪 / 差分，点击“传立绘”即可自动创建对应目录。
- **预设切换**：在“立绘 (Character)”面板中，新增“角色分组”下拉框。每个预设都可以记住自己的角色组，渲染时会根据文本情绪在该角色组下寻找对应差分，找不到则回退到其他角色 / 内置立绘。
- **命名规范**：角色名称仅允许英文、数字、下划线、连字符，若输入其他字符会自动转换为 `_`。

---

## 关键配置说明（_conf_schema.json）

- **基础开关**
  - `enable_render`：是否拦截文本并尝试渲染为图片。
  - `render_char_threshold`：**渲染字符阈值**，0 为不限制；超过该长度则直接发送纯文本（推荐约 60 个汉字）。

- **情绪相关**
  - `enable_emotion_prompt`：是否自动注入情绪提示语。
  - `emotion_prompt_template`：自动提示模板，支持 `{tags}` 占位符。
  - `emotion_sets`：声明可用情绪标签 / 对应立绘文件夹 / 颜色的列表，可按需增删。
  - `default_emotion`：当文本中未出现标签时使用的情绪 key。

- **字体与渲染**
  - `font_path`：可选。如需在本地 Pillow 渲染中使用自定义字体，可填写字体文件的绝对路径。
  - `image_type`：输出图片格式，支持 `png` / `jpeg`。

- **WebUI 访问**
  - `webui_host` / `webui_port`：WebUI 监听地址与端口。
  - `webui_token`：访问 WebUI 所需的 token。

---

## 注意事项

- 插件主要依赖 Pillow 进行图像渲染，请确保运行环境中安装了对应依赖。
- 未检测到背景或立绘文件时，会自动降级为纯背景 / 无立绘模式，保证消息仍可正常发送。
- 若在其他插件中也修改了 `event.get_result()` 或拦截消息，请注意插件执行顺序以及 `event.stop_event()` 的使用，避免互相覆盖。

![dfc325accb815446a2b4503599c9efc3_720](https://github.com/user-attachments/assets/41acac86-de9d-4bf1-8acc-3a985affc53f)


---

## 更新日志

### v1.6.0
- 预设管理面板新增状态提示与“覆盖当前 / 另存为”按钮，应用或保存后会自动刷新角色组与立绘预览。
- `/切换预设` 指令兼容 `*切换预设` 等写法，聊天内切换更顺手。
- “资源上传”区改为卡片式布局，立绘上传时可同时指定角色分组与情绪，流程提示更清晰。
- README 更新至 v1.6.0，补充新版交互说明。

### v1.5.0
- WebUI 上传立绘支持「情绪 / 差分」选择框，自动读取 `emotion_sets` 并可填写自定义目录。
- 新增“角色分组”概念，目录结构升级为 `characters/<角色>/<情绪>/文件`；预设可独立选择角色组，渲染时会按角色 + 情绪匹配差分。
- 用户立绘会在“预览立绘”选择器中按 `用户/角色/情绪/文件` 展示，便于定位。
- README、元数据同步到 v1.5.0，文档补充差分上传与目录结构说明。
