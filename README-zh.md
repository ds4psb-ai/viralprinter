# viralprinter

[English](README.md) · [한국어](README-ko.md) · 简体中文

**生成器产出视频，viralprinter 产出结构。**

面向短视频的合成器与结构 linter。把一条短视频写成声明式 JSON，用 ffmpeg 渲染成
mp4，并按爆款结构规则给任何一条短视频打分——包括 AI 视频生成器直接吐出的结果。

状态：v0。时间线格式 `0.1`，规则为 `provisional`。[DESIGN.md](DESIGN.md) 中的
接口在 v0 期间冻结，其余部分仍可能变动。

## 它做什么

**给任何短视频打分。** `viralprinter grade` 接受一个 mp4 或一份时间线 JSON，返回一张
评分卡：钩子窗口、剪辑节奏、时长适配、结构完整性、文字密度。它不关心文件从哪儿
来——手机、剪辑软件，或者一个把十五秒丢给你、却对该在哪儿下刀毫无主张的生成器。
测量只用 ffmpeg 和 ffprobe，任何内容都不会被上传。

**把时间线合成为 mp4。** `viralprinter compose` 将声明式时间线——节拍、镜头、文字、
音频——渲染成成片。本地、确定性、无账号、无密钥。活由 ffmpeg 干，viralprinter 决定
递给它什么。

**用 agent 驱动整个闭环。** [SKILL.md](SKILL.md) 是分发面：粘贴一句话，就能让
Claude Code、Cursor 或任何 agent CLI 从一个想法走到拍摄包、时间线、成片，直到
评分卡。

刻意不设总分。这张卡本身就是结果——每一项都带着测到了什么、和哪条区间比较、
以及这条区间为什么存在的一句话。取平均等于凭空造出规则并不具备的精度。

## 快速开始

### 用 agent（推荐路径）

往任何能读 skill 的 agent CLI 里粘贴一句话：

```
Use this skill: https://raw.githubusercontent.com/ds4psb-ai/viralprinter/main/SKILL.md — make me a shooting packet for TOPIC
```

接下来 agent 会自行照着 SKILL.md 走：做拍摄包、用你的素材写时间线、校验、合成、
给结果打分，并把绝对路径交回给你。同样的写法，别的活儿：

```
Use this skill: https://raw.githubusercontent.com/ds4psb-ai/viralprinter/main/SKILL.md — grade this short: ./out.mp4
Use this skill: https://raw.githubusercontent.com/ds4psb-ai/viralprinter/main/SKILL.md — I liked this one: <短视频链接>, make me one like it
```

`https://raw.githubusercontent.com/ds4psb-ai/viralprinter/main/SKILL.md` 是本仓库 `SKILL.md` 的 raw URL。

### 手动

```
git clone https://github.com/ds4psb-ai/viralprinter && cd viralprinter
uv pip install -e .          # 或：pip install -e .

viralprinter validate examples/hook-payoff-916.json
viralprinter compose  examples/hook-payoff-916.json -o out.mp4
viralprinter grade    out.mp4 --markdown
```

需要 Python ≥ 3.11，且 `ffmpeg` 与 `ffprobe` 在 `PATH` 上。示例时间线指向
`clips/*.mp4`，合成前请换成你自己的素材。

### 证据包（可选）

打分与合成只需要这个仓库。*证据*那一半——趋势谱系、可借用的公式、来自真实分析
片段的分镜包——来自 Shorti 的只读 MCP 入口，需要主动开启：

```
claude mcp add --transport http shorti https://api.shorti.ai/mcp/public-read/mcp
```

按契约只读：它不会发布、修改、删除、扣费，也不会接收你的素材。如果你只想打分或
合成，可以完全跳过。

## 时间线格式

把短视频写成代码。节拍以绝对秒计，已排序且互不重叠；`role` 取
`hook | development | payoff | cta | other` 之一。

```json
{
  "version": "0.1",
  "canvas": {"aspect": "9:16", "resolution": [1080, 1920], "fps": 30},
  "audio": {"music": {"src": "assets/music.mp3", "gain_db": -18}},
  "beats": [
    {
      "id": "hook",
      "role": "hook",
      "t": [0.0, 1.2],
      "shot": {"src": "clips/01.mp4", "in": 3.4, "framing": "close"},
      "text": {"content": "wait for it", "pos": "center"},
      "cue": "cold open on the reveal, no logo"
    }
  ],
  "subtitles": {"mode": "none"},
  "provenance": {"packet": "shorti-packet-<slug>.md"}
}
```

必填：`version`、`canvas`、`beats`，以及每个节拍的 `t` 与 `shot`。其余全部可选
——不知道的值就省略，不要臆填。完整示例见 [`examples/`](examples/)，其中含一份
[评分卡示例](examples/example-scorecard.md)。

## 诚实的缺席

某一项在给定输入上无法测量时，报告带原因的 `state: not_measured`，而不是猜一个
分数。节拍角色无法从像素还原，所以一个成片理所当然会留下空行——想填上就去给
时间线打分。schema 无法表达的合成输入是校验错误，而不是被悄悄丢弃。

这是特性。带两处诚实空白的卡片，比五个自信满满、其中两个是编出来的数字更有
信息量。

## 这里发布什么，不发布什么

- `grade/rules/*.yaml` 是本仓库唯一源自私有语料的产物，而且只以**粗粒度的类别
  与区间**形式存在。v0 的取值由人工设定，并标注 `provenance: provisional`。语料
  行、embedding、测量 schema、prompt 文本、模型名称都不在本仓库中，将来也不会有。
- 区间描述的是在已分析片段中反复出现的结构。它们不是效果预测，`out_of_band`
  是一个值得回答的问题，而不是缺陷。
- 永远不存在服务端密钥。未来的 provider 适配器从*你的*环境读取 key，在客户端
  运行，除了 provider 自家的 API 之外不向任何地方传输。
- 除了两项主动开启的功能——显式的 provider 渲染调用，以及 Shorti 桥接——
  其余一切都在离线环境下运行。

## 路线图

- **Provider 适配器**（`providers/`）——自带 key 的生成，全程在客户端进行，
  让时间线可以取得磁盘上还没有的镜头。
- **Shorti 桥接**（`shorti/`）——直接把证据包转成时间线草稿，不必再由 agent
  手工誊写。
- **规则 v1**——用一次基于测量的蒸馏流程重新生成区间，并摘掉
  `provenance: provisional`。

## 许可证

MIT，见 [LICENSE](LICENSE)。
