# viralprinter

[English](README.md) · 한국어 · [简体中文](README-zh.md)

**생성기는 영상을 찍어낸다. viralprinter는 구조를 찍어낸다.**

숏폼 영상을 위한 컴포저이자 구조 린터. 숏폼을 선언적 JSON으로 쓰고, ffmpeg로
mp4로 렌더하고, 어떤 숏폼이든 — AI 영상 생성기가 그대로 뱉은 결과물까지 —
바이럴 구조 규칙에 비추어 채점한다.

상태: v0. 타임라인 포맷 `0.1`, 규칙은 `provisional`. [DESIGN.md](DESIGN.md)의
인터페이스는 v0 동안 동결이고, 그 밖은 아직 움직일 수 있다.

## 무엇을 하는가

**어떤 숏폼이든 채점한다.** `viralprinter grade`는 mp4나 타임라인 JSON을 받아
스코어카드를 낸다: 훅 구간, 컷 밀도, 길이 적합도, 구조 완결성, 텍스트 밀도.
파일이 어디서 왔는지는 따지지 않는다 — 휴대폰이든, 편집기든, 컷을 어디 둘지에
대한 의견 없이 15초를 건네준 생성기든. 측정은 ffmpeg와 ffprobe뿐이고, 아무것도
업로드하지 않는다.

**타임라인을 mp4로 합성한다.** `viralprinter compose`는 선언적 타임라인 — 비트,
샷, 텍스트, 오디오 — 을 완성 파일로 렌더한다. 로컬, 결정론적, 계정도 키도 없다.
일은 ffmpeg가 하고, viralprinter는 ffmpeg에 무엇을 건넬지 정한다.

**루프 전체를 에이전트로 돌린다.** [SKILL.md](SKILL.md)가 배포면이다. 한 번
붙여넣으면 Claude Code, Cursor, 그 밖의 어떤 에이전트 CLI든 아이디어에서 촬영
패킷으로, 타임라인으로, 렌더된 파일로, 스코어카드까지 간다.

총점은 일부러 없다. 카드 자체가 결과다 — 각 항목이 무엇을 쟀는지, 어떤 밴드와
비교했는지, 그 밴드가 왜 있는지를 한 문장으로 함께 싣는다. 평균을 내면 규칙에
없는 정밀도를 지어내는 셈이다.

## 빠른 시작

### 에이전트로 (의도된 경로)

스킬을 읽는 아무 에이전트 CLI에 한 문장만 붙여넣으면 된다:

```
Use this skill: https://raw.githubusercontent.com/ds4psb-ai/viralprinter/main/SKILL.md — make me a shooting packet for TOPIC
```

그다음은 에이전트가 SKILL.md를 따라 알아서 한다. 패킷을 만들고, 당신의 클립으로
타임라인을 쓰고, 검증하고, 합성하고, 결과를 채점하고, 절대경로를 돌려준다. 같은
패턴의 다른 작업:

```
Use this skill: https://raw.githubusercontent.com/ds4psb-ai/viralprinter/main/SKILL.md — grade this short: ./out.mp4
Use this skill: https://raw.githubusercontent.com/ds4psb-ai/viralprinter/main/SKILL.md — I liked this one: <숏폼 링크>, make me one like it
```

`https://raw.githubusercontent.com/ds4psb-ai/viralprinter/main/SKILL.md`은 이 저장소 `SKILL.md`의 raw URL이다.

### 손으로

```
git clone https://github.com/ds4psb-ai/viralprinter && cd viralprinter
uv pip install -e .          # 또는: pip install -e .

viralprinter validate examples/hook-payoff-916.json
viralprinter compose  examples/hook-payoff-916.json -o out.mp4
viralprinter grade    out.mp4 --markdown
```

Python 3.11 이상, 그리고 `ffmpeg`와 `ffprobe`가 `PATH`에 있어야 한다. 예제
타임라인은 `clips/*.mp4`를 가리키므로, 합성 전에 당신의 소스로 바꿔라.

### 증거 패킷 (선택)

채점과 합성에는 이 저장소 말고 아무것도 필요 없다. *증거* 쪽 — 트렌드 계보,
차용 공식, 분석된 실제 클립의 샷별 키트 — 는 Shorti의 읽기 전용 MCP 문에서 오고,
옵트인이다:

```
claude mcp add --transport http shorti https://api.shorti.ai/mcp/public-read/mcp
```

계약상 읽기 전용이다. 올리거나 고치거나 지우거나 결제하지 않고, 당신의 미디어를
받지도 않는다. 채점이나 합성만 할 거라면 통째로 건너뛰어도 된다.

## 타임라인 포맷

코드로 쓴 숏폼. 비트는 절대 초이고, 정렬되어 있으며 겹치지 않는다. `role`은
`hook | development | payoff | cta | other` 중 하나다.

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

필수는 `version`, `canvas`, `beats`, 그리고 비트마다 `t` + `shot`. 나머지는 전부
선택이다 — 모르는 값은 채우지 말고 빼라. 전체 예제는 [`examples/`](examples/),
[스코어카드 예시](examples/example-scorecard.md)도 함께 있다.

## 정직한 부재

주어진 입력에서 잴 수 없는 채점 항목은 추측한 점수 대신 이유와 함께
`state: not_measured`를 보고한다. 비트의 역할은 픽셀에서 복원되지 않으므로,
렌더된 파일은 정당하게 몇 줄을 비운 채로 나온다 — 그 줄을 채우려면 타임라인을
채점하라. 스키마가 표현할 수 없는 컴포저 입력은 조용한 누락이 아니라 검증
오류다.

이건 기능이다. 정직한 빈칸 두 개가 있는 카드가, 그중 둘은 지어낸 자신만만한
숫자 다섯 개보다 더 많이 알려준다.

## 무엇이 실리고 무엇이 실리지 않는가

- `grade/rules/*.yaml`만이 비공개 코퍼스에서 유래한 산출물이고, 그것도 **성긴
  범주와 밴드**로만이다. v0 값은 손으로 정했고 `provenance: provisional`로
  표시된다. 코퍼스 행, 임베딩, 측정 스키마, 프롬프트 텍스트, 모델 이름은 이
  저장소에 없고 앞으로도 없다.
- 밴드는 분석된 클립들에서 반복된 구조를 서술한다. 성과 예측이 아니며,
  `out_of_band`는 결함이 아니라 답해볼 만한 질문이다.
- 서버 측 비밀은 영원히 없다. 앞으로 들어올 프로바이더 어댑터는 *당신의*
  환경에서 키를 읽고, 클라이언트에서 돌고, 프로바이더 자신의 API 외에는
  어디로도 보내지 않는다.
- 옵트인 두 가지 — 명시적인 프로바이더 렌더 호출, 그리고 Shorti 브리지 — 를
  빼면 전부 오프라인에서 돈다.

## 로드맵

- **프로바이더 어댑터** (`providers/`) — 키는 사용자가 가져오고 전부
  클라이언트에서 도는 생성. 디스크에 없는 샷을 타임라인이 조달할 수 있게 된다.
- **Shorti 브리지** (`shorti/`) — 에이전트가 손으로 옮겨 적는 대신, 증거
  패킷에서 곧바로 초안 타임라인을 만든다.
- **규칙 v1** — 측정 기반 증류 패스로 밴드를 재생성하고
  `provenance: provisional`을 뗀다.

## 라이선스

MIT. [LICENSE](LICENSE) 참조.
