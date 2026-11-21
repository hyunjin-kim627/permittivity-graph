# 유전율 그래프 측정 (permittivity-graph)

논문 그림을 캡처한 **유전율(ε) vs 온도(T) 그래프 이미지(PNG)** 에서
곡선을 색깔별로 찾아 **수치를 자동으로 읽어내는** 파이썬 도구입니다.
그래프 디지타이저(digitizer)를 이 용도에 맞춰 만든 것입니다.

각 곡선(조성 x)마다 다음 값을 **오차와 함께** 계산합니다.

- **최대 유전율(peak ε)** 과 그때의 **온도(peak T, 큐리 온도 근처)**
- **상온(room T)에서의 유전율**
- 지정한 온도 구간 안의 **최소 유전율**
- 모든 곡선 중 전체 최대 / 최소

오차가 너무 큰 값(기본: 상대오차 10% 초과)은 `읽기불가`로 표시하고,
결과는 **텍스트 파일**과 **검증용 오버레이 이미지**로 저장합니다.

---

## 파일 구성

| 파일 | 설명 |
|---|---|
| `permittivity_digitizer.py` | ⭐ **통합 파일.** 컬러 모드 + 흑백 모드 + 설정(프리셋)을 모두 담은 한 파일. 이 파일 하나만 있으면 됨 (아래 "한 파일로 실행") |
| `read_permittivity_plot.py` | 컬러 그래프용 스크립트. 설정 파일(JSON)을 읽어 어떤 그래프든 처리하는 범용 버전 |
| `read_permittivity_plot_adapted.py` | 30–110 °C 그래프 1개 전용으로 축 값·색을 코드에 직접 적어 둔 **이전 버전**. 검은 곡선(x=0)은 처리하지 않음 |
| `config_ba_sr.json` | (Ba₁₋ₓSrₓ)(Zr₀.₁Ti₀.₉)O₃ 그래프(−150~150 °C, x = 0.05~0.45, 5개 곡선)용 설정. **기본 설정** |
| `config_dielectric_x1000.json` | 유전상수(×1000) vs T 그래프(30~110 °C, x = 0~0.09, 6개 곡선)용 설정 |
| `화면 캡처 test_results.txt` | `config_dielectric_x1000.json`으로 돌린 결과 예시 |
| `화면 캡처 test_overlay.png` | 위 결과의 오버레이 이미지(검출한 곡선과 피크 표시) |
| `.gitignore` | 캐시, 가상환경, `.env`, Office 임시 파일 등을 Git에서 제외 |
| `requirements.txt` | 필요한 파이썬 패키지 목록 |
| `bw_test/` | **흑백 그래프용** 디지타이징 (아래 "흑백 그래프 읽기" 참고) |

> 원본 그래프 이미지(`화면 캡처 test.png`)는 이 폴더가 아니라 `OneDrive\사진`에 있습니다.

---

## 설치 (처음 한 번)

Python 3.10 이상이 필요합니다. 아래 명령은 Windows PowerShell 기준입니다.

```powershell
git clone https://github.com/hyunjin-kim627/permittivity-graph.git
cd permittivity-graph
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

- `.venv`는 이 프로젝트 전용 가상환경입니다. 다른 프로젝트의 패키지와 섞이지 않습니다. `.gitignore`에 들어 있어서 GitHub에는 올라가지 않습니다.
- 다음부터는 터미널을 열 때마다 `.\.venv\Scripts\Activate.ps1`만 실행하면 됩니다.
- `Activate.ps1` 실행이 막히면 `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`를 한 번 실행하거나, 활성화하지 않고 `.\.venv\Scripts\python.exe`로 직접 실행하세요.
- macOS / Linux에서는 `source .venv/bin/activate`를 씁니다.

패키지: `numpy`, `Pillow`, `scipy`, `openpyxl`(엑셀 저장용). 목록은 [requirements.txt](requirements.txt)에 있습니다.

---

## 한 파일로 실행 (`permittivity_digitizer.py`)

`read_permittivity_plot.py`(컬러), `bw_test`의 흑백 스크립트 5개, JSON 설정 2개를 **한 파일로 합친 것**입니다.
설정(프리셋)이 파일 안에 들어 있어서, 이 파일과 그래프 이미지만 있으면 됩니다.
기존 파일들과 **결과가 완전히 같은 것**을 확인했습니다(텍스트, 오버레이, 엑셀 데이터 모두 동일).

| 모드 | 명령 | 하는 일 |
|---|---|---|
| `color` | `python permittivity_digitizer.py color 이미지.png --preset x1000` | 색으로 곡선 구분 → 피크·상온·최소 ε와 오차. 결과 txt, 오버레이 png, **엑셀(xlsx)** 저장 |
| `bw` | `python permittivity_digitizer.py bw` | 흑백 그래프를 가이드 경로로 따라가서 → 엑셀(데이터+차트) + 검증 이미지 저장 |
| `presets` | `python permittivity_digitizer.py presets --outdir 폴더` | 내장 설정을 JSON 파일로 꺼냄 → 새 그래프용 설정을 만들 때 복사해서 고침 |

**컬러 모드 옵션**
- `--preset ba_sr` (기본) 또는 `--preset x1000`: 내장 설정 사용
- `--config 설정.json`: 직접 만든 설정 파일 사용(형식은 기존 `config_*.json`과 같음)
- `--outdir 폴더`: 결과 저장 위치(기본: 이미지와 같은 폴더)

**흑백 모드 옵션**
- 옵션 없이 실행하면 내장된 BaTiO₃ 프리셋(Fig.1, Fig.2a~c)을 `bw_test` 폴더의 이미지로 실행
- `--config 설정.json`: 다른 흑백 그래프용 설정(형식은 `presets`로 꺼낸 `preset_bw_BaTiO3.json` 참고)
- `--images 폴더`: 설정에 적힌 이미지 파일이 있는 폴더
- `--outdir 폴더`: 엑셀과 검증 이미지 저장 위치(기본: `--images` 폴더)

예시:

```powershell
python permittivity_digitizer.py color "C:\Users\user\OneDrive\사진\화면 캡처 test.png" --preset x1000
```

```powershell
python permittivity_digitizer.py bw --outdir 결과
```

설정 파일의 모든 항목은 `permittivity_digitizer.py` 맨 위 설명(docstring)에 정리되어 있습니다.

---

## 사용법

```powershell
python -I read_permittivity_plot.py 이미지.png --config config_dielectric_x1000.json
```

| 옵션 | 뜻 |
|---|---|
| `이미지.png` | 읽을 그래프 캡처 이미지 |
| `--config` | 설정 파일. 생략하면 `config_ba_sr.json` 사용 |
| `--outdir` | 결과를 저장할 폴더. 생략하면 이미지와 같은 폴더 |

실행하면 다음 두 파일이 만들어집니다.

- `<이미지이름>_results.txt`: 수치 결과 표
- `<이미지이름>_overlay.png`: 3배 확대한 이미지 위에 검출 결과를 그린 것
  - 점: 검출한 곡선 중심선
  - 초록 십자 + 라벨: 검출한 피크
  - 회색 박스: 곡선을 찾은 영역
  - 분홍 박스: 무시한 영역(범례, 삽입 그래프)

**결과를 믿기 전에 꼭 오버레이 이미지를 눈으로 확인하세요.**
색 규칙이 맞지 않으면 엉뚱한 픽셀을 곡선으로 잡을 수 있습니다.

---

## 흑백 그래프 읽기 (`bw_test/`)

색으로 곡선을 구분할 수 없는 흑백 논문 그림(BaTiO₃ 입자 크기별 ε–T, Fig.1과 Fig.2 a·b·c)을 읽는 예제입니다.

```powershell
cd bw_test
python make_excel.py
```

| 파일 | 설명 |
|---|---|
| `calib.py` | 각 그래프의 축 눈금 픽셀 위치 → 값 보정 |
| `trace.py` | 가이드 경로 근처의 검은 선 픽셀을 열(급경사는 행) 단위로 따라가는 함수 |
| `curves_fig1.py`, `curves_fig2.py` | 곡선별 대략적인 경로(가이드)와 무시할 영역(라벨, 화살표) |
| `make_excel.py` | 위를 모두 실행해 엑셀과 검증 이미지를 만듦 |
| `BaTiO3_흑백그래프_디지타이징.xlsx` | 결과: 설명 시트 + 그래프별 데이터 시트와 차트 |
| `검증_Fig*.png` | 읽은 점을 원본 위에 색깔로 표시한 확인용 이미지 |

새 흑백 그래프에 쓰려면 `calib.py`에 축 눈금 위치를, `curves_*.py`에 곡선 경로를 새로 적어야 합니다.

👉 동작 원리, 주요 결과, 검증 이미지, 한계, 새 그래프에 적용하는 방법은 **[bw_test/README.md](bw_test/README.md)** 에 자세히 정리했습니다.

---

## 동작 원리

1. **축 보정(calibration)**: 픽셀 위치를 온도·유전율 값으로 바꾸는 직선식(값 = a·픽셀 + b)을 구합니다.
   - `auto_ticks`: 이미지에서 축 눈금을 자동으로 찾음
   - `points`: `[픽셀, 값]` 쌍을 직접 지정(2개 이상)
2. **곡선 추출**: 설정 파일의 색 규칙(RGB 또는 HSV 조건식)에 맞는 픽셀을 곡선별로 골라냅니다.
   범례나 삽입 그래프 같은 영역은 `ignore`로 뺍니다.
3. **값 계산**: 열(온도)마다 곡선의 위/중앙/아래 픽셀을 구해 피크, 상온 값, 최소값을 계산합니다.
   선 두께만큼(`mark_half_px`) 보정해 선의 중심을 기준으로 합니다.
4. **오차 전파**: 픽셀을 읽을 때의 오차(`sigma_px`, 기본 1.5 px)를 온도·유전율 오차로 바꾸고,
   상대오차가 `rel_limit`보다 크면 `읽기불가`로 표시합니다.
5. **오버레이 저장**: 사람이 직접 검증할 수 있도록 결과를 그림으로 남깁니다.

---

## 설정 파일(JSON) 항목

| 키 | 뜻 |
|---|---|
| `name` | 설정 이름(설명용) |
| `x_axis`, `y_axis` | `{"auto_ticks": [...]}` 또는 `{"points": [[픽셀, 값], ...]}` |
| `plot_box` | `[행0, 행1, 열0, 열1]`, 곡선을 찾을 영역(`auto_ticks`일 때는 생략 가능) |
| `ignore` | `[[행0, 행1, 열0, 열1], ...]`, 건너뛸 영역 |
| `room_T` | 상온 값(°C) |
| `T_range` | 최소값을 찾을 온도 구간 |
| `sigma_px` | 픽셀 읽기 오차(1σ, **가정값**) |
| `mark_half_px` | 선 두께의 절반(px) |
| `smooth_window` | 피크를 찾기 전 적용하는 중앙값 필터 폭(열 개수) |
| `rel_limit` | 이 값보다 상대오차가 크면 `읽기불가` |
| `curves` | 곡선 목록: `name`, `color`(오버레이 색), `rule`(색 조건식), 그리고 선택 항목 `rows`, `cols`, `ignore`, `min_component_px` |

`rule`에서 쓸 수 있는 변수: `R`, `G`, `B`(0–255), `H`(0–360), `S`(0–1), `V`(0–255)

> ⚠️ `rule`은 파이썬 `eval()`로 실행됩니다. **직접 작성했거나 믿을 수 있는 설정 파일만** 사용하세요.

새 그래프에 쓰려면 기존 config 하나를 복사해서 축 값, 영역, 곡선 색 규칙을 그 그래프에 맞게 고치면 됩니다.

---

## 예시 결과 (`config_dielectric_x1000.json`)

- 보정값: 0.298 °C/px, 207.5 ε/px → 읽기 오차 약 ±0.45 °C, ±311 ε
- 그래프에 보이는 온도 범위: 30.7 ~ 109.4 °C

| 조성 x | 최대 ε | 피크 온도 (°C) | 30 °C에서 ε |
|---|---|---|---|
| 0 | 11103 ± 311 | 60.4 ± 1.6 | 4049 ± 311 |
| 0.01 | **39109 ± 311** | 55.3 ± 0.4 | 9409 ± 312 |
| 0.03 | 22928 ± 311 | 52.9 ± 0.4 | 6746 ± 311 |
| 0.05 | 23550 ± 311 | 55.4 ± 1.3 | 9028 ± 311 |
| 0.07 | 23758 ± 311 | 52.5 ± 0.6 | 7161 ± 311 |
| 0.09 | 19401 ± 311 | 53.2 ± 1.3 | 8406 ± 311 |

- 전체 최대: x = 0.01에서 39109 (55.3 °C)
- 최소값은 모두 `읽기불가`: 곡선이 구간 전체에서 검출되지 않았거나, 아래 축에 닿아 정확히 읽을 수 없음

---

## 주의할 점

- `sigma_px`는 **가정값**입니다. 실제 오차는 이미지 해상도와 선 두께에 따라 다릅니다.
- 곡선끼리 겹치는 부분(예: 고온 쪽 꼬리)에서는 어떤 곡선의 값인지 구분이 어렵습니다.
- 상온이 그래프 범위 밖이면 상온 값 대신 가장자리 값을 `참고`로만 출력합니다.
- 해상도가 낮은 캡처일수록 오차가 커집니다. 가능하면 크게 캡처하세요.

---

## 저장소

GitHub: https://github.com/hyunjin-kim627/permittivity-graph
