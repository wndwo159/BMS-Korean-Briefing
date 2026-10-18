# BMS Korean Briefing

Falcon BMS 4.38용 한국어 브리핑 뷰어와 인게임 니보드 생성기입니다. Falcon BMS 공식 제품이 아닌 커뮤니티 애드온입니다.

## 설치

[최신 배포](https://github.com/wndwo159/BMS-Korean-Briefing/releases/latest)에서 **BMS-Korean-Briefing-Setup.exe**를 내려받아 실행하세요. Python 설치는 필요 없습니다.
설치 프로그램이 BMS 설치 경로를 자동 감지합니다. 여러 설치본은 목록에서 고르거나 직접 폴더를 선택할 수 있습니다.
프로그램은 선택한 BMS의 `User/Plugins/BMS-Korean-Briefing`에 설치됩니다.

## 사용

BMS 실행 → BRIEFING의 PRINT → 한국어 브리핑 자동 표시. 설정은 바탕화면 뷰어 바로가기로 게임 없이도 열 수 있습니다.
니보드 생성은 현재 HTML 문서의 표·글꼴·종이 디자인을 캡처해 KTO/F-16 니보드에 적용합니다. 첫 페이지 배치와 A4 비율 보정을 지원합니다.
원본 브리핑은 수정하지 않으며, 니보드 원본은 자동 백업합니다.

## 업데이트

앱 시작 시 새 정식 배포를 확인합니다. **설정 → 업데이트**에서 새 버전 확인 및 다운로드·설치를 할 수 있습니다.
GitHub에서 공개한 설치 파일을 SHA-256과 크기로 검증한 뒤 기존 경로에 업데이트하고 뷰어를 다시 엽니다. 설정·기록·번역본은 유지합니다.

## 개발

Windows / Python 3.12에서 `./build.ps1`을 실행합니다. 빌드 시 고정 체크섬의 오프라인 번역 모델을 설치합니다.
배포 방법은 [RELEASING.md](RELEASING.md)를 참고하세요.

## 번역과 뷰어

기본 오프라인 엔진은 Argos EN→KO 1.1 모델을 CTranslate2/SentencePiece로 CPU int8 추론합니다. BMS 라벨·반복 문구에는 검토한 번역을 사용하고 일반 설명은 신경망으로 번역합니다. 숫자·시간·주파수·호출부호·계급/인명·군사 약어는 분리해 보존 검증합니다. 실패 항목은 영어를 유지합니다. 원문 의미가 완전히 보장되는 것은 아니므로 한영 병기를 제공합니다.

Watchdog+폴링, 파일 쓰기 안정 확인, SHA-256 중복 억제, UTF-8 HTML 원자적 저장을 지원합니다. HTML/HTM과 실제 BMS briefing.txt를 읽습니다. g_sBriefingsDirectory 설정을 설치 시 읽고, 뷰어 설정에서도 경로를 바꿀 수 있습니다. 원본은 수정·삭제하지 않습니다.

뷰어는 실제 섹션 탐색, 한국어/영어/병기, 표·기록·검색·재번역·인쇄/PDF·KST 보조 표시를 제공합니다. 저장 HTML에는 CSS와 한영 전환이 들어 있어 서버 종료 후 단독 열기가 가능합니다. 원본 파일별 최신 번역을 보관하며 모든 PRINT 버전을 별도 스냅샷으로 보관하지 않습니다.

게임 전체 화면 포커스 강제 전환은 기본 OFF입니다. 브라우저 연결 상태를 15초 기준으로 판정하므로 백그라운드 탭 정지 시 재사용 판정이 늦어질 수 있습니다. pywebview는 포함하지 않습니다.

Ollama/Argos/OpenAI는 선택 가능한 별도 엔진입니다. OpenAI는 사용자가 명시적으로 선택하고 환경변수 OPENAI_API_KEY를 설정한 경우에만 원격 전송합니다. 기본 오프라인 엔진은 번역 중 원격 호출이 없습니다.

## 개발 및 재현 빌드

Python 3.12 설치 후 `./setup.ps1`, `./.venv/Scripts/python.exe entrypoint.py`로 개발 서버를 실행합니다. 설치된 앱은 인수 없이 수동 서버, `--with-bms --profile <ID>`로 BMS 연동, `--attach-bms`로 실행 중인 BMS 연결을 지원합니다. 프로필과 경로는 설치기의 install.json에 저장됩니다.

`./build.ps1`은 테스트 후 앱 EXE→모델/라이선스/안내서 payload→설치 EXE→배포 ZIP·소스 ZIP 순서로 생성합니다. `setup.ps1`은 공식 모델 하나(약 121MB)를 다운로드하고 SHA-256을 검증합니다. 배포 EXE에는 모델이 포함됩니다.

앱 상태: http://127.0.0.1:8765/api/health
종료: 같은 Origin으로 POST /api/shutdown (설치된 세션 서버 지원)
검증: `./.venv/Scripts/python.exe -m pytest -q`

## 검증 범위

2026-10-17: 사용자 실제 PRINT 후 자동 열기와 동일 뷰어 유지 확인. 실제 briefing.txt 143개 항목을 설치된 EXE에서 오프라인 번역하여 보호 검증 오류 0건 및 저장 확인. HTML 샘플은 없어 fixture 검증만 수행했습니다. 현재 게임을 재시작하지 않고 --attach-bms로 설치 경로의 EXE를 확인했습니다. 런처 실행 대기·종료·빠른 재시작은 자동 테스트로 검증했으며 실제 게임 재시작 전체 흐름은 사용자 환경에서 추가 확인할 수 있습니다. 깨끗한 다른 Windows PC에서의 설치 테스트는 미수행입니다.

자동 테스트는 파일 감시/중복/갱신/원문/표/실제 신경망 추론/숫자·인명 보호/알 수 없는 섹션/세션 수명/단일 실행/경로 감지/바로가기 COM 왕복/백업·복원/데이터 이전/손상 배포본 거부를 검사합니다. 설치 EXE에는 내장 payload 체크섬 및 Tcl/Tk 런타임 자체검증 모드가 있습니다.

자체 소스는 MIT, 제3자 모델·라이브러리는 동봉 THIRD-PARTY-NOTICES와 licenses의 조건을 따릅니다. 모델 출처는 https://github.com/argosopentech/argospm-index 이며 모델 라이선스 확인은 https://github.com/argosopentech/argos-translate/issues/533 입니다.

0.2.1: Launcher.exe가 Alternative Launcher로 전환되는 동안 감시기가 종료되던 문제를 수정했습니다. 두 원본 런처의 실행 경로를 함께 확인하고, 두 런처 모두 종료된 뒤에도 게임 로딩을 최대 180초 기다립니다. 런처 UI가 열려 있으면 대기를 계속합니다.

## Paper UI revision

문서 중심 A4 화면, 아이보리 종이·약한 질감·백보드·분류 탭으로 UI를 재설계했습니다. 번역/파서/감시/런처 로직은 유지하며 main.py의 document() HTML 템플릿만 변경했습니다. source CSS와 JS는 paper-theme.css 및 paper_document.js이고 build_ui.py가 내장 글꼴을 포함한 viewer.html/standalone.html/briefing.css를 생성합니다. 화면 확인 자료는 ui-review/, 디자인 및 검증 범위는 UI-DESIGN-NOTES.md에 있습니다. 배포 ZIP은 dist/BMS-Korean-Briefing-0.2.1-paper-ui-Windows-x64.zip입니다.


군사 고유명사 보호: military_terms.py의 검토된 무장명·기지명은 AI에 보내지 않고 지정 표기로 복원합니다. 무장 구성 행과 미등록 영문 비행장명은 추측 번역 대신 영어를 보존합니다. 숫자·좌표·주파수 검증은 유지합니다. 사전 버전은 캐시 키와 브리핑 기록에 포함되어 업데이트 후 같은 PRINT도 새 규칙으로 처리합니다. 별도의 대형 모델 설치 없이 내장 CPU 번역 엔진에서 동작하며 Ollama/OpenAI 경로에도 고유명사 보호를 적용합니다.


10. 선택 사항: Ollama 로컬 AI 모델 설치와 선택
기본 내장 번역은 추가 설치 없이 사용할 수 있습니다.
뷰어의 [설정] → [번역 엔진]에서 [Ollama · 로컬 AI 모델 선택·설치]를 고릅니다.
안내의 공식 Windows 설치 페이지에서 Ollama를 설치하고 실행합니다.
[연결·모델 목록 다시 확인]을 누릅니다. 설치되어 있지만 실행되지 않았다면 [설치된 Ollama 실행]을 누릅니다.
다운로드 목록에서 TranslateGemma 4B(약 3.3 GB) 또는 12B(약 8.1 GB)를 고르고 [선택한 모델 다운로드·설치]를 누릅니다.
진행률과 오류를 표시하며 취소할 수 있습니다. 앱을 종료하면 앱에서 진행 중인 다운로드도 중단 요청합니다.
다시 다운로드하면 Ollama에서 이미 받은 부분을 재사용할 수 있습니다.
완료 후 [설치된 Ollama 모델] 목록에서 선택하고 [설정 저장]을 누릅니다. 현재 문서를 새 모델로 재번역합니다.
기존에 Ollama로 설치한 다른 모델도 자동 목록에 표시됩니다. 이름을 외워 입력할 필요가 없습니다.
다운로드 완료만으로 번역 엔진을 바꾸지는 않습니다. 기본 내장 엔진으로 언제든 돌아올 수 있습니다.
4B/12B는 다운로드 크기이며 실제 실행 메모리는 별도입니다. 로컬 AI는 게임과 GPU/RAM을 공유합니다.
설치된 모델 파일은 브리핑 앱 폴더가 아니라 Ollama가 관리하는 저장 위치에 남습니다.
참고: https://ollama.com/download/windows / https://ollama.com/library/translategemma


11. BMS 없이 설정·기록 열기
바탕화면 [BMS Korean Briefing Viewer] 바로가기 또는 설치 폴더의 BMS-Korean-Briefing-Viewer.exe를 실행하세요.
BMS 실행이나 PRINT 없이 기본 브라우저에서 설정과 저장된 브리핑을 열 수 있습니다.
서버가 꺼져 있으면 이때만 시작하고, 이미 켜져 있으면 기존 서버를 사용합니다. BMS 게임은 실행하지 않습니다.
모든 브리핑 뷰어 탭을 닫고 약 30초가 지나면 수동 뷰어 서버가 종료됩니다. BMS 실행 중이면 PRINT 처리를 위해 유지합니다.
BMS를 먼저 실행한 경우에도 이 EXE로 뷰어를 열면, 게임을 종료한 뒤 열려 있는 뷰어에서 설정을 계속 사용할 수 있습니다.
상시 설정 서버는 등록하지 않습니다. 기존 로그인 실행 감지기는 BMS 런처/게임 시작만 감지합니다.
http://127.0.0.1:8765 주소는 서버가 실행 중일 때 사용할 수 있으므로, 꺼져 있을 때는 뷰어 EXE를 먼저 실행하세요.
