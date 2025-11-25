# 传话筒（astrbot_plugin_chuanhuatong）

将 AstrBot 的所有纯文本回复转换成带立绘的 GalGame 风聊天框图片，支持情绪差分、多段富文本与拖拽式 WebUI 布局设置。
<img width="2030" height="886" alt="image" src="https://github.com/user-attachments/assets/b507f5c7-121a-4183-9a13-ee2e1f5e1832" />
<img width="1600" height="600" alt="image" src="https://github.com/user-attachments/assets/064d8964-b09a-4b94-9b64-d062b45d0f69" />
<img width="469" height="244" alt="image" src="https://github.com/user-attachments/assets/7a37b40e-0419-415d-a908-d66692b7045d" />

## 功能特性

- ✅ 拦截 Bot 输出的文本，在发送前统一转为图片，失败时自动降级为原始文本
- 🎨 自动抽取背景 / 立绘素材：`background/`、`renwulihui/<情绪>/`，WebUI 可实时预览
- 😳 支持 LLM 情绪提示：在回答中嵌入 `&happy&`、`&shy&` 等标签即可切换立绘
- 🔧 内置 WebUI，可拖拽主文本框、名字、情绪角标、立绘位置，直接写回配置
- 📝 额外文本层可无限新增，支持独立字体/颜色/透明度/图层顺序
- 🍮 完全基于本地 Pillow 渲染，无需 Playwright；如渲染失败会自动退回纯文本
- 🧰 端口/token、情绪映射等在 `_conf_schema.json` 中调节，其余布局交给 WebUI

## 安装

1. 将整个目录放入 `AstrBot/data/plugins/astrbot_plugin_chuanhuatong`
2. 在 AstrBot WebUI → 插件管理中启用插件，并根据需要修改配置
3. 如果要启用 WebUI，请确保 `webui_host`/`webui_port` 未被占用

## WebUI

- 默认监听 `http://127.0.0.1:18765`，可通过 `?token=xxx` 或 `Authorization: Bearer xxx` 访问
- 画布内可拖拽 / 缩放：主文本框、名字、情绪角标、立绘框及所有额外文本/图片层
- 图层列表支持查看/选择/删除，类似 Photoshop，可调节 z-index、透明度、可见性
- 表单中可指定字体（系统字体 / 上传字体）、背景资源、情绪角标颜色等
- “上传资产”区可直接上传 PNG/WebP 到 `zujian/`，或上传 TTF/TTC/OTF 字体到 `fonts/`
- 配置保存在 `data/plugin_data/astrbot_plugin_chuanhuatong/layout_state.json`，刷新 / 重载插件不会丢失

## 情绪标签

- 插件会在 LLM 请求阶段追加提示，要求模型在回答中插入 `&tag&`
- 默认标签：`&happy&`、`&sad&`、`&shy&`、`&surprise&`、`&angry&`、`&neutral&`
- 也可以关闭自动提示，然后在其他插件/Prompt 中手写标签

## 资源放置

```
astrbot_plugin_chuanhuatong/
├── background/          # 背景图，支持 png/jpg/webp，随机抽取
└── renwulihui/
    ├── happy/
    ├── sad/
    ├── shy/
    └── surprise/
```

立绘建议使用透明 PNG，文件名任意。可以自由新增子目录，然后在配置的 `emotion_sets` 中指向这些目录。

### 数据目录（自动创建）

```
AstBot/data/plugin_data/astrbot_plugin_chuanhuatong/
├── layout_state.json   # WebUI 保存的布局
├── zujian/             # WebUI 上传的额外组件（PNG/WebP）
└── fonts/              # WebUI 上传的字体文件
```

将素材 / 字体直接放入上述目录也可以被 WebUI 识别。

## 配置重点

- `enable_render`：是否拦截文本
- `enable_emotion_prompt`：是否自动注入情绪提示语（配置项 `emotion_prompt_template` 支持 `{tags}` 占位符）
- `emotion_sets`：一个列表，用来声明可用的情绪标签 / 对应立绘文件夹 / 角标颜色，可根据需求增删
- `font_path`：可选。若需要在本地 Pillow 备用渲染里使用自定义字体，填写字体文件的绝对路径
- `webui_port` / `webui_token`：自定义 WebUI 端口和访问口令；文本框、名字、额外文本请在 WebUI 中拖拽完成

## 注意事项

- 插件仅依赖 Pillow；如需使用自定义字体，可在 WebUI 中上传或设置 `font_path`
- 如果未检测到背景或立绘文件，会自动降级为纯背景/无立绘模式
- 若在其他插件中也修改了 `event.get_result()`，请注意执行顺序及 `event.stop_event()` 的影响
