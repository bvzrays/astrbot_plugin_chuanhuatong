<div align="center">

#  ✨ 传话筒（astrbot_plugin_chuanhuatong）✨
<img width="300" height="300" alt="image" src="https://github.com/user-attachments/assets/6af41d2d-f0d1-4be5-a656-b1fe748c8a5d" />

## 公网环境请注意配置token！
> **当前版本：v1.7.0**

<img width="525" height="238" alt="image" src="https://github.com/user-attachments/assets/b9a86fcb-8621-4191-941f-55013090d118" />


</div>

将 AstrBot 的纯文本回复转换成带立绘的 GalGame 风聊天框图片，支持情绪差分、多层文本、拖拽式 WebUI 布局与自定义组件模板。

<img width="627" height="703" alt="image" src="https://github.com/user-attachments/assets/833d053d-383d-4e6b-941d-4936869d3e4c" />


---

## 使用场景

- **聊天对话美化**：所有回复统一渲染为带立绘的对话框图片
- **多情绪立绘**：通过在文本中插入 `&happy&` / `&sad&` 等标签，自动切换对应情绪立绘。
- **自定义 UI 布局**：在 WebUI 中拖拽主文本框、角色立绘、多个文本 / 图片 / 毛玻璃层，做成自己的聊天框模板。

---

## 主要特性

- **统一图片渲染**
  - 拦截 Bot 输出的文本，在发送前统一转为图片，渲染失败自动降级为原始文本。
  - 支持渲染字符阈值：过长文本自动退回纯文本，避免文字溢出。

- **自动背景 / 立绘管理**
  - 自动从 `background/`、`renwulihui/<情绪>/` 等目录中随机抽取素材。
  - 支持 `__auto__` / `__random__` 模式，也可以在 WebUI 中指定固定立绘。

- **情绪标签驱动立绘**
  - 在回答中插入 `&happy&`、`&shy&`、`&angry&` 等标签即可切换对应情绪立绘。
  - 情绪集合、对应子目录、颜色等由 `_conf_schema.json` 的 `emotion_sets` 统一管理。

- **WebUI 布局编辑**
  - 所见即所得编辑画布：可拖拽 / 缩放主文本框、角色立绘、文本层、图片组件、毛玻璃层。
  - 图层列表类似 Photoshop：支持调整 z-index、透明度、可见性、删除等。
  - 文本层支持自定义字体、字号、颜色、**描边宽度 / 颜色**，边框可拖拽控制自动换行与字体自适应。

- **多预设保存 / 一键切换**
  - WebUI 保存时可输入名称，自动写入 `data/.../presets/*.json`，方便管理不同剧本皮肤。
  - 在任何对话中发送 `/切换预设 预设名`（兼容 `*切换预设` 写法），即可即时切换到指定布局，无需离开聊天窗口。
  - 预设管理面板内置“覆盖当前”“另存为”按钮，实时刷新角色组与立绘预览，所见即所得。

- **立绘角色分组 + 差分**
  - WebUI 上传立绘前，可先选择“角色分组”，再选择情绪/差分目录，或分别填写自定义名称。
  - 插件会自动落盘到 `plugin_data/.../characters/<角色>/<情绪>/`，预设中可指定某个角色组，渲染时会根据情绪标签自动切换该角色组下的对应差分。

- **组件与毛玻璃模板**
  - 可以将对话框外框、按钮、角标等作为“组件图层”摆放。
  - 毛玻璃效果作为独立图层存在，可与主文本框分离，放在任意位置。

- **回退**
  - 如渲染出错会自动回退为纯文本发送，保证消息不丢失。

<img width="1920" height="1312" alt="image" src="https://github.com/user-attachments/assets/d313b111-94f6-42bd-8976-122f23d46d82" />

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
   - 可在配置中修改 `webui_host` / `webui_port`，请确保端口未被其他程序占用，若无法进入webui则优先检查防火墙，再尝试重启bot框架。

<img width="1004" height="1079" alt="image" src="https://github.com/user-attachments/assets/f1af9e28-2d45-4a4b-9c51-1dfbdbd746cd" />


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

<img width="339" height="198" alt="image" src="https://github.com/user-attachments/assets/bb26cd55-6222-4ce5-a97a-c7f29159e0df" />


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

<img width="614" height="668" alt="image" src="https://github.com/user-attachments/assets/638262b1-ce88-44f8-a4bd-2111edafda76" />


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

<img width="581" height="185" alt="image" src="https://github.com/user-attachments/assets/5a31444a-9991-4384-9b22-2afe4df0d7d0" />


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

<img width="742" height="340" alt="image" src="https://github.com/user-attachments/assets/b9e36b2d-dd5f-4f8f-80e3-510b9be906cd" />


---

### 立绘角色分组

- **目录层级**：推荐结构为 `characters/<角色>/<情绪>/<文件>`，角色名和情绪名均可自定义；
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

<img width="1280" height="480" alt="c8a942fee1751694aa04c49771e204a0_720" src="https://github.com/user-attachments/assets/26b138ee-f4a3-47a4-a660-4b5b087a77fc" />


---

## 插件内置《魔法少女的魔女审判》全角色预设下载
**请到 https://github.com/bvzrays/astrbot_plugin_chuanhuatong-Magical-Girl-Witch-Trials 下载模板和立绘**
<img width="1600" height="600" alt="e44d70c03555daa6057b2ac702bd3d43" src="https://github.com/user-attachments/assets/f9522646-463c-4879-b174-480509711e02" />
<img width="1600" height="600" alt="c74f77dfb7e1ce3180f206da0e8c8a22" src="https://github.com/user-attachments/assets/c21df64c-d5f1-4eb0-8728-dc36a5ceee3c" />
<img width="1600" height="600" alt="ce38ffc9fb01a02142c8c8453b69e57f" src="https://github.com/user-attachments/assets/5150af2b-dc5b-465b-9132-6350e6eaedd6" />
<img width="1600" height="600" alt="1417f5d131b57a2ccb09278b056b84ce" src="https://github.com/user-attachments/assets/dbb16290-521f-4158-845b-c0a0c4c10fba" />
<img width="1600" height="600" alt="4907720c7bbe1148dfd1aaeb1f02ef45" src="https://github.com/user-attachments/assets/0bdcb8d9-33b4-4998-b245-95741317864c" />
<img width="1600" height="600" alt="cf0b0ba02c2abc855ca2df975a1f14b2" src="https://github.com/user-attachments/assets/3275d0d5-70b9-49b7-88bb-61dd79ff1449" />
<img width="1600" height="600" alt="ec8bd6ccf0f9dd57472b3c92a0ff84fb" src="https://github.com/user-attachments/assets/acb17108-22a4-4c04-8b9e-41565be5d9d0" />
<img width="1600" height="600" alt="6e8d4c78c0d9ed7825e2978ca1040b7c" src="https://github.com/user-attachments/assets/4598afc5-a469-4a46-bc4c-00a050699fb3" />
<img width="1600" height="600" alt="16a36d6b7e539163c2a88f24eca77001" src="https://github.com/user-attachments/assets/395ec728-fd14-4766-b486-0d3c3f4a1d8e" />
<img width="1600" height="600" alt="48e77c8ce9ff43b3052eec5dfbd2d3bc" src="https://github.com/user-attachments/assets/45279711-1c03-476d-ae38-8468270f7d89" />
<img width="1600" height="600" alt="909cadd9d92025668c9954bcf1413d7d" src="https://github.com/user-attachments/assets/0242f3cb-f3ec-4f00-9717-cbea0917a538" />
<img width="1600" height="600" alt="60e499029f905c74da834b0d1b0a6fc0" src="https://github.com/user-attachments/assets/06839ac8-877d-495d-9116-196cfd0fa7a5" />
<img width="1600" height="600" alt="4aa64bbae0dd16fd5d644355d553a370" src="https://github.com/user-attachments/assets/185bf155-1f2e-4102-b2e9-d6dece552472" />
<img width="1600" height="600" alt="416687fb4a0c077dd964d599af26a92a" src="https://github.com/user-attachments/assets/5e696af3-b04c-4fe9-be0a-e1dd5a3e5627" />


## 更新日志

### v1.7.0
- 修复指令问题，确保框架配置的命令符正常工作
- 修复预设导入后立绘错乱：加载预设后自动刷新缓存和角色列表，确保立绘正确显示
- 修复表情标签清理：在 `on_decorating_result` 钩子中清理 `&xxx&` 格式的情绪标签，确保从文本和对话历史中完全移除
- 修复插件冲突：调整事件钩子优先级，确保与 `continuous_message` 等插件兼容，若仍有冲突可自行修改优先级

### v1.6.0
- 预设管理面板新增状态提示与“覆盖当前 / 另存为”按钮，应用或保存后会自动刷新角色组与立绘预览
- “资源上传”区改为卡片式布局，立绘上传时可同时指定角色分组与情绪

### v1.5.0
- WebUI 上传立绘支持「情绪 / 差分」选择框，自动读取 `emotion_sets` 并可填写自定义目录
- 新增“角色分组”概念，目录结构升级为 `characters/<角色>/<情绪>/文件`；预设可独立选择角色组，渲染时会按角色 + 情绪匹配差分
- 用户立绘会在“预览立绘”选择器中按 `用户/角色/情绪/文件` 展示，便于定位
