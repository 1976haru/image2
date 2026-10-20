# image2 — CHILI LAB Story Image Studio

**목표:** Windows RTX 3060 12GB / RAM 32GB에서 ComfyUI를 로컬 엔진으로 사용하여, 반복 가능한 고품질 YouTube 이미지 4장을 만드는 프로그램. 개발은 Claude Code 중심, Codex 리뷰, GitHub PR 중심.

## 중요: 현재 단계
이 저장소의 feature 브랜치는 **품질 우선 개발 기반·설계 문서** 단계입니다. 과거 V1.3.1의 4장 생성 코드가 아직 이 저장소에 이관되지 않았습니다. V1.3.1을 그대로 정상 작동한다고 주장하지 마세요. 아래 마이그레이션 작업이 선행되어야 합니다.

## 3개의 분리된 제품 모드
1. **STORY_ANIME**: 10~20곡을 담은 이야기 JSON → 기승전결 독립 이미지 4장, 남자/여자/남녀 시점, 남녀 별도 레퍼런스. 누락된 얼굴 참조를 텍스트 프롬프트만으로 '유지 성공'이라고 보고하지 말 것.
2. **MIO_MORNING**: 6줄 NO/PLAYLIST_CODE/状況/MAIN_TEXT/DISPLAY_TEXT/EMOTIONAL_LINE → 현실 사진 A/B/C/D 4장. 사람이 등장하면 실패. 이미지에서 글자를 생성하지 않고 프로그램으로 정확한 채널명과 DISPLAY_TEXT를 합성한다.
3. **HARU_LITTLE_CAFE**: Mio와 같은 6줄 입력이지만 일본 동네 작은 카페, 음료·창가·자연광·생활감, 인물 금지.

## 완료 정의
- 실제 GPU 샘플: 4개가 **독립된 장면**, 16:9, 인물/장면 정책을 충족.
- 출력 ZIP은 **최종 JPG 네 개만**, 원본/source/업스케일 복제본 없음.
- 레퍼런스에 사용한 경로와 선택한 실제 모델이 실행 전 리포트에 명시됨.
- 한 장 실패 시 원인 기록, 결과를 합격으로 포장하거나 더미 이미지로 치환 금지.
- 4K는 원본 4K가 아닌 경우 반드시 업스케일이라고 기록.
- Windows CI 통과와 실제 RTX 3060 실사용 PASS는 **별도 상태**로 보고.

## 시작하기 (Claude Code)
1. 이 저장소를 D:\ai\image2 에 clone.
2. 로컬 V1.3.1 프로젝트의 Python 코드/테스트만 이관한다. 아래 `scripts/import_v131.ps1` 확인.
3. `CLAUDE.md`, `docs/ARCHITECTURE.md`, `docs/QUALITY_GATES.md`, `docs/PHASE1.md` 순서로 읽는다.
4. 우선 GPU 실생성 전 사전 점검과 이미지 1장 품질 비교 테스트를 구축한다.
5. 브랜치에서 커밋/PR. 사용자 승인 없이 main merge, 강제 push, local 삭제 금지.

## 안전과 저작권
저장소는 **public**. 가사 원문, 저작물 레퍼런스 사진, 개인 작업물, 모델 가중치(safetensors), 생성 결과, API 키를 GitHub에 올리지 마세요. 실제 리소스는 PC D:에 보관하고 테스트에는 합성 데이터를 사용하세요.

무료 로컬 실행에도 전기료와 모델별 상업용 라이선스 조건은 별도입니다. 장면·인물 유사도와 아트워크 품질을 보장하지 않습니다.

[품질 개발 명세](docs/PHASE1.md) · [연동 구조](docs/ARCHITECTURE.md) · [품질 판정](docs/QUALITY_GATES.md)