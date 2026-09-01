# assets

| 파일 | 용도 | 규격 |
|------|------|------|
| `logo.png` | 헤더 / 푸터 워드마크 (배경 투명) | 높이 200px 이상 권장 |
| `logo-white.png` | 어두운 배경용 (선택) | 위와 동일 |
| `favicon.png` | 브라우저 탭 아이콘 | 512×512 |
| `og.jpg` | 카카오·페북 공유 썸네일 | 1200×630 |

로고 원본(흰 배경 PNG/JPG)이 있으면 아래 한 줄로 위 3개가 한 번에 생성됩니다.

```bash
pip install pillow
python landing/tools/logo_cutout.py ~/Downloads/obliv-logo.png
```

`logo.png` 가 없어도 페이지는 깨지지 않습니다 — Cormorant Garamond 로 조판된
`Obliv Clinic` 텍스트 워드마크가 자동으로 대체 표시됩니다.
