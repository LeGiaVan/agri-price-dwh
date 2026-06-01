# Contributing Guide — agri-price-dwh

Tài liệu này mô tả **quy trình làm việc nhóm** để đảm bảo code sạch, không conflict và dễ review.

---

## 1. Nguyên tắc chung

- **Không bao giờ commit thẳng lên `main`** — kể cả nhóm trưởng (trừ lần setup đầu tiên).
- **Mỗi task = 1 nhánh riêng** — xong task mới merge.
- **Commit thường xuyên** — mỗi buổi làm việc ít nhất 1 commit, đừng để dồn.
- **Không commit file `.env`** — chứa token bí mật, đã được gitignore.
- **Kéo code mới nhất trước khi bắt đầu làm** — tránh conflict.

---

## 2. Nhánh (Branch) của từng thành viên

| Thành viên | Nhánh | Mô tả |
|---|---|---|
| Nhóm trưởng | `main` | Chỉ merge PR vào đây |
| Thành viên 1 | `feature/ingest-pipeline` | ingest scripts + GitHub Actions |
| Thành viên 2 | `feature/dbt-silver-gold` | dbt Silver & Gold models |
| Thành viên 3 | `feature/ml-forecasting` | ARIMA, LSTM, SHAP notebooks |
| Thành viên 4 | `feature/dashboard-genbi` | Streamlit app + Groq chatbot |

---

## 3. Quy trình làm việc (mỗi ngày)

### Bước 1 — Lấy code mới nhất

```bash
git checkout main
git pull origin main
git checkout feature/ten-nhanh-cua-ban
git merge main          # cập nhật code mới nhất vào nhánh của bạn
```

### Bước 2 — Viết code & commit

```bash
# Sau khi code xong một phần nhỏ
git add .
git commit -m "feat: mo ta ngan gon ban da lam gi"
```

### Bước 3 — Push lên GitHub

```bash
git push origin feature/ten-nhanh-cua-ban
```

### Bước 4 — Tạo Pull Request (khi xong task)

1. Vào GitHub repo → tab **Pull requests** → **New pull request**
2. Base: `main` ← Compare: `feature/ten-nhanh-cua-ban`
3. Tiêu đề PR: mô tả ngắn gọn task đã làm
4. Description: điền checklist bên dưới
5. Assign **nhóm trưởng** làm reviewer
6. Nhóm trưởng review và merge

---

## 4. Quy ước đặt tên

### Tên nhánh

```
feature/ten-tinh-nang    # tính năng mới
fix/ten-loi              # sửa lỗi
docs/cap-nhat-tai-lieu   # cập nhật tài liệu
refactor/ten-phan        # refactor code
```

**Ví dụ tốt:**
```
feature/fao-ingest-script
feature/silver-price-cleaning
fix/null-handling-worldbank
docs/update-readme
```

### Commit message

Dùng cấu trúc: `type: mô tả ngắn gọn`

| Type | Khi nào dùng |
|---|---|
| `feat` | thêm tính năng mới |
| `fix` | sửa bug |
| `docs` | cập nhật tài liệu |
| `refactor` | sửa code không thay đổi logic |
| `test` | thêm/sửa tests |
| `chore` | cấu hình, dependencies |

**Ví dụ tốt:**
```
feat: add fao_ingest.py with retry logic
feat: add silver_fao_prices dbt model
fix: handle null price values in worldbank data
docs: update README with quickstart guide
chore: pin duckdb version to 1.1.3
```

**Tránh viết:**
```
update file          # quá chung chung
fix bug              # bug gì?
wip                  # không mô tả gì
.                    # không chấp nhận
```

---

## 5. Checklist trước khi tạo Pull Request

Dán checklist này vào description PR và tick từng mục:

```markdown
## Checklist

### Code
- [ ] Code chạy không lỗi trên máy local
- [ ] Không có file .env, token, password trong commit
- [ ] Đã xử lý các trường hợp lỗi (try/except, None check)
- [ ] Đã thêm comment cho đoạn code phức tạp

### Ingest (Thành viên 1)
- [ ] Script chạy được với docker-compose
- [ ] Log ghi rõ số dòng đã nạp
- [ ] GitHub Actions workflow trigger thành công
- [ ] Dữ liệu xuất hiện trên MotherDuck

### dbt (Thành viên 2)
- [ ] `dbt run --select ten_model` chạy không lỗi
- [ ] `dbt test --select ten_model` tất cả tests pass
- [ ] Đã viết description cho mỗi column trong schema.yml

### ML (Thành viên 3)
- [ ] Notebook chạy từ đầu đến cuối không lỗi
- [ ] Đã ghi RMSE/MAPE vào model_evaluation.md
- [ ] Bảng forecast đã có trong MotherDuck
- [ ] Model weights (.h5) đã được commit

### Dashboard (Thành viên 4)
- [ ] App chạy local không lỗi (streamlit run app.py)
- [ ] Tất cả biểu đồ hiển thị đúng
- [ ] Chatbot trả lời được bằng tiếng Việt
- [ ] URL Streamlit Cloud đã cập nhật vào README
```

---

## 6. Xử lý conflict

Khi `git merge main` báo conflict:

```bash
# 1. Xem file nào bị conflict
git status

# 2. Mở file đó, tìm đoạn có dấu <<<<<
# Chọn giữ code nào (của bạn hay của main), xóa dấu <<<< ==== >>>>

# 3. Sau khi sửa xong
git add ten-file-da-fix.py
git commit -m "fix: resolve merge conflict in ten-file"
```

Nếu không chắc giữ code nào → **hỏi nhóm trưởng** trước khi tự sửa.

---

## 7. Quy tắc bảo mật

> ⚠️ **QUAN TRỌNG** — Vi phạm các quy tắc này có thể làm lộ token và bị tính phí.

- **KHÔNG** commit file `.env`
- **KHÔNG** hardcode token trong code: `token = "md_abc123"` ← SAI
- **LUÔN** đọc token từ biến môi trường: `os.getenv("MOTHERDUCK_TOKEN")`
- Nếu lỡ commit token → báo nhóm trưởng **ngay lập tức** để revoke token cũ và tạo token mới

---

## 8. Liên hệ khi cần hỗ trợ

| Vấn đề | Hỏi ai |
|---|---|
| Lỗi kết nối MotherDuck | Nhóm trưởng |
| Lỗi dbt model | Thành viên 2 |
| Lỗi ingest / GitHub Actions | Thành viên 1 |
| Lỗi ML / Colab | Thành viên 3 |
| Lỗi Streamlit / deploy | Thành viên 4 |