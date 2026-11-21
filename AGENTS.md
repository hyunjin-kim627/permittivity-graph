# AGENTS.md

AI 코딩 에이전트(OpenCode, Claude Code 등)가 이 저장소에서 작업할 때 먼저 읽는 안내서입니다.
사람을 위한 설명은 [README.md](README.md)와 [bw_test/README.md](bw_test/README.md)에 있습니다.

## 프로젝트 한 줄 요약

논문 그림을 캡처한 **유전율(ε) vs 온도(T) 그래프 이미지**에서 곡선을 찾아 **수치를 읽어내는** 파이썬 디지타이저.
사용자는 재료(BaTiO₃, BZT, BST 계열 강유전체) 연구자이며, 결과는 주로 **엑셀**로 받기를 원합니다.

## 대화 언어와 스타일

- 사용자와는 **한국어**로 대화합니다. 커밋 메시지도 한국어로 씁니다(기존 이력 참고: `git log --oneline`).
- 사용자는 Git과 파이썬에 익숙하지 않습니다. 명령은 그대로 복사해서 실행할 수 있게 주고, 무엇을 하는 명령인지 짧게 설명하세요.
- 결과를 말할 때는 **확인한 것과 확인하지 못한 것을 구분**하고, 추정한 값은 "추정"이라고 밝히세요.

## 파일 구조

| 경로 | 역할 |
|---|---|
| `permittivity_digitizer.py` | ⭐ **메인. 통합 파일.** 컬러 모드 + 흑백 모드 + 내장 프리셋. 새 기능은 여기에 추가합니다. |
| `read_permittivity_plot.py` | 컬러 모드의 원래 스크립트. 통합 파일과 결과가 같아야 하는 **기준(reference)** |
| `read_permittivity_plot_adapted.py` | 그래프 1개 전용 이전 버전. 더 이상 고치지 않음 |
| `config_ba_sr.json`, `config_dielectric_x1000.json` | 컬러 모드 설정. 통합 파일에 `ba_sr`, `x1000` 프리셋으로 같은 내용이 들어 있음 |
| `bw_test/` | 흑백 모드의 원래 스크립트들(`calib.py`, `trace.py`, `curves_fig1.py`, `curves_fig2.py`, `make_excel.py`)과 예제 이미지·결과 엑셀·검증 이미지 |
| `requirements.txt` | 패키지 목록: numpy, Pillow, scipy, openpyxl |

## 환경

- Windows 11, PowerShell, **Python 3.10**, 프로젝트 폴더는 OneDrive 안(`문서\유전율_그래프_측정`)
- 가상환경: `.venv` (`.gitignore`에 포함)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 실행 명령

```powershell
# 컬러 그래프 (내장 프리셋 ba_sr 또는 x1000, 또는 --config 설정.json)
python permittivity_digitizer.py color "이미지.png" --preset x1000 --outdir 결과

# 흑백 그래프 (내장 BaTiO3 프리셋, 이미지는 bw_test 폴더에서 찾음)
python permittivity_digitizer.py bw --outdir 결과

# 새 그래프 1단계: 테두리와 축 눈금 픽셀 자동 검출 -> txt, 번호 붙인 확인 이미지, bw 설정 초안 JSON
python permittivity_digitizer.py ticks "이미지.png" --outdir 결과

# 내장 프리셋을 JSON으로 내보내기 (새 그래프 설정의 템플릿)
python permittivity_digitizer.py presets --outdir 설정
```

- **새 그래프는 `ticks`부터 하세요.** 눈금 픽셀을 별도 스크립트로 찾지 마세요. 사람(또는 에이전트)이 할 일은 ① 확인 이미지의 눈금 번호와 그림 라벨을 맞춰 `x_ticks[1]`/`y_ticks[1]`에 값 적기, ② 곡선 가이드 적기, 두 가지뿐입니다.
- `ticks`는 닫힌 사각형 테두리만 찾습니다. 범례 상자를 그래프로 잡거나 축만 있는 그래프면 `--box top,bottom,left,right`를 쓰세요. 확인 이미지를 반드시 열어 보세요.
- 가이드는 사람이 눈으로 정하는 값입니다. 결과를 보고할 때 "숫자는 픽셀에서 읽었고, 어느 선이 어느 곡선인지는 판단"이라는 점을 구분해서 말하세요.

- 컬러 모드 예제 이미지는 저장소에 없습니다. 사용자 PC의 `C:\Users\user\OneDrive\사진\화면 캡처 test.png`(x1000 프리셋용)와 `새 폴더\화면 캡처 2026-11-15 220459.png`(ba_sr 프리셋용)에 있습니다.
- 흑백 모드 예제 이미지는 `bw_test/fig1_BaTiO3_grainsize.png`, `bw_test/fig2_BaTiO3_3transitions.png`에 있습니다.
- 사용자 파일을 덮어쓰지 않도록, 시험 실행은 **항상 `--outdir`로 임시 폴더를 지정**하세요.

## 코드를 고친 뒤 꼭 할 검증

테스트 프레임워크는 없습니다. 대신 **기존 결과와 똑같이 나오는지 비교**합니다.

1. **컬러 모드:** 같은 이미지·설정으로 `read_permittivity_plot.py`와 `permittivity_digitizer.py color`를 각각 실행하세요.
   - `_results.txt`는 첫 두 줄(image/config 경로)과 마지막 줄(overlay 경로)을 뺀 나머지가 같아야 합니다.
   - `_overlay.png`는 픽셀 단위로 같아야 합니다.
2. **흑백 모드:** `permittivity_digitizer.py bw --outdir 임시폴더`의 결과를 `bw_test/BaTiO3_흑백그래프_디지타이징.xlsx`와 비교하세요.
   - Fig1, Fig2a, Fig2b, Fig2c 시트의 모든 셀 값이 같아야 합니다.
   - `검증_*.png`는 픽셀 단위로 같아야 합니다.
3. 결과가 **일부러 바뀌는** 수정이라면, 무엇이 왜 바뀌었는지 사용자에게 설명하고 확인을 받은 뒤 기준 파일을 갱신하세요.
4. 숫자만 보지 말고 **오버레이/검증 이미지를 직접 열어 보세요.** 곡선 위에 점이 올라가 있어야 제대로 읽은 것입니다.

## 동작 원리 요약

- **컬러 모드:** 축 눈금을 자동으로 찾거나(`auto_ticks`) 픽셀↔값 쌍(`points`)으로 보정합니다. 설정의 `rule`(R,G,B,H,S,V 조건식)으로 곡선 픽셀을 골라 피크, 상온 값, 최소값을 구합니다. 픽셀 오차(`sigma_px`)를 전파해서, 상대오차가 `rel_limit`보다 크면 `읽기불가`로 표시합니다.
- **흑백 모드:** 곡선마다 사람이 정한 **가이드 경로**(k배 확대 crop 기준 좌표, 원점 `(left-2, top-2)`)를 따라갑니다. 열마다(거의 수직인 구간은 `mode: "y"`로 행마다) 가이드에서 `W` px 안에 있는 가장 가까운 검은 선의 중심을 읽습니다. 그다음 일정한 T 간격으로 보간합니다.
- 새 흑백 그래프를 지원하려면 코드가 아니라 **설정(JSON)** 을 새로 만들면 됩니다. `presets`로 꺼낸 `preset_bw_BaTiO3.json` 형식을 따르세요.

## 하지 말 것 / 주의할 것

- **`git add .`나 `git add -A`를 쓰지 마세요.** 바꾼 파일을 하나씩 지정해서 add하세요.
  - `새 폴더/`에는 논문 그림 캡처(png)와 출판 논문 원문(PDF, 저작권)이 함께 있습니다. 사용자가 **그림·캡처는 올리고 원문은 올리지 않기로** 했습니다.
    - `*.pdf`와 PDF 내용을 html 이름으로 저장한 `새 폴더/10.1063_1.322330.html`은 `.gitignore`로 빠져 있습니다. **`git add -f`로 강제로 올리지 마세요.**
    - 새 논문을 받으면 PDF는 그대로 두고, 그림을 캡처한 png만 커밋합니다.
  - `digitize_<날짜>/` 같은 실행 결과 폴더도 사용자가 올리기로 했습니다(예: `digitize_20261121/`). Claude가 만든 결과는 파일 이름에 `_claude`를 붙여 다른 도구의 결과와 구분합니다.
- **commit과 push는 사용자가 요청할 때만** 하세요.
- `requirements.txt`는 **ASCII만** 쓰세요. 한글 주석이 있으면 한국어 Windows(cp949)의 pip 22.x가 파일을 읽지 못합니다.
- `bw_test/trace.py`는 파이썬 표준 모듈 `trace`와 이름이 같습니다. `bw_test` 스크립트는 그 폴더 안에서 `sys.path.insert(0, '.')`로 실행해야 합니다. 통합 파일에는 이 문제가 없습니다.
- 설정의 `rule`은 `eval()`로 실행됩니다. 사용자가 직접 만들었거나 믿을 수 있는 설정 파일만 쓰세요.
- 흑백 Fig1의 curve B·C·D가 각각 2.2·3.0·13 µm라는 것은 **추정**입니다. 확정된 값처럼 쓰지 마세요.
- 논문 그림 이미지는 저작권이 있습니다. 저장소를 공개로 바꾸거나 새 논문 그림을 올릴 때는 사용자에게 먼저 알리세요.
- 콘솔 출력에 한글이 있으니, 새 스크립트에서도 `sys.stdout.reconfigure(encoding="utf-8")`를 유지하세요.

## 참고: 흑백 예제의 출처

`bw_test`의 그림은 Kinoshita & Yamaji (1976), *J. Appl. Phys.* 47, 371 (입자 크기에 따른 BaTiO₃ 세라믹 유전 특성)에서 나온 것으로 **추정**됩니다. 사용자의 `새 폴더`에 있는 파일 이름(`kinoshita1976_fig1.png`, `10.1063_1.322330`)을 근거로 했습니다.
