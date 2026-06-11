# Kế hoạch Tạo luồng Cron Job Cập nhật Dữ liệu Hàng Ngày

Tôi đã hiểu chính xác ý đồ kiến trúc của bạn! Bạn muốn tách bạch rõ ràng giữa 2 luồng:
1. **Luồng Batch (Historical Load):** Giữ nguyên các file code hiện tại. Luồng này dùng để chạy thủ công bằng tay (hoặc chạy 1 lần) để kéo dữ liệu của 2 năm hoặc 20 năm về nhằm "xây nền móng" cho Database ban đầu.
2. **Luồng Cron Job (Daily Incremental Load):** Viết riêng 1 script mới tinh. Luồng này được thiết kế cực nhẹ và nhanh, chỉ dành riêng cho Github Actions tự động chạy mỗi đêm để kéo đúng dữ liệu của ngày hôm đó đắp thêm vào.

Dưới đây là kế hoạch chi tiết để thực hiện đúng ý tưởng này:

---

## 1. Xây dựng Script cho Cron Job (`ingest/daily_cron.py`)

Tôi sẽ tạo một file hoàn toàn mới tên là `ingest/daily_cron.py`. File này sẽ thực hiện các bước sau mỗi đêm:

- **Bước 1:** Kết nối vào MotherDuck, chạy lệnh `SELECT MAX(price_date) FROM bronze.yf_prices_raw` để tìm ngày lấy cuối cùng.
- **Bước 2:** Gọi hàm lấy dữ liệu của Yahoo Finance (và World Bank nếu có bản tin mới) nhưng chỉ bắt đầu từ `max_date` tìm được ở Bước 1. (Ví dụ: `yf.download(start=max_date)`).
- **Bước 3:** Gắn thêm logic **Fallback / Retry**: Nếu gọi API bị lỗi hoặc timeout do mạng, script sẽ thử lại tối đa 3 lần. Nếu vẫn thất bại, nó sẽ ghi log báo lỗi và đóng an toàn chứ không làm sập Database.
- **Bước 4:** Nạp (INSERT) 1-2 dòng dữ liệu mới của ngày hôm nay vào bảng.

*Tác dụng:* Việc này hoàn toàn không đụng chạm hay làm hỏng code của các file `yf_ingest.py` hay `worldbank_ingest.py` cũ của bạn. Các file cũ vẫn đóng vai trò là "Batch Historical Load".

---

## 2. Giải quyết bài toán Dữ liệu bị rỗng (Thứ 7, Chủ Nhật) bằng dbt

Dù Cron Job có chạy thành công, Yahoo Finance cũng sẽ không trả về dữ liệu cho Thứ 7 và Chủ Nhật. Để Dashboard và mô hình ML không bị "thủng" dữ liệu, ta sẽ xử lý nội suy (Imputation) bằng dbt.

- **Kỹ thuật Fill Forward:** Tôi sẽ sửa file `dbt/models/gold/fact_price_daily.sql`. Trong file này, tôi sẽ dùng `CROSS JOIN` bảng `dim_date` để tạo ra một trục thời gian liên tục. Sau đó dùng lệnh SQL:
  ```sql
  LAST_VALUE(price_usd_per_kg IGNORE NULLS) OVER (
      PARTITION BY commodity ORDER BY price_date
  )
  ```
  Lệnh này sẽ tự động "nhìn ngược về quá khứ" để kéo mức giá có thực gần nhất (ví dụ: giá Thứ 6) điền lấp đầy cho ngày Thứ 7 và Chủ Nhật bị trống. Đảm bảo dữ liệu 100% liền mạch.

---

## 3. Cập nhật file GitHub Actions (`ingest.yml`)

Cuối cùng, cập nhật lại luồng tự động để liên kết toàn bộ hệ thống:

1. Chạy `python ingest/daily_cron.py` để kéo duy nhất dữ liệu ngày hôm nay.
2. (Mới thêm) Chạy lệnh `dbt build` ngay sau đó. Dbt sẽ tự động lấy dữ liệu mới ở tầng Bronze, tự động Fill Forward dữ liệu Thứ 7/CN và đắp lên tầng Gold.

---

## User Review Required

> [!IMPORTANT]
> Với kế hoạch này: File cũ giữ nguyên để làm Batch, tạo thêm file mới tinh chuyên làm Cron Job tự động cập nhật hàng ngày.
> 
> Bạn có đồng ý với phương án này chưa? Nếu "Đồng ý", tôi sẽ tạo file `ingest/daily_cron.py` mới và tiến hành viết code ngay bây giờ!

---

## Câu hỏi phản biện cần trả lời trước khi code

> Mục tiêu của phần này là khóa rõ hành vi mong muốn trước khi viết cron job, vì hiện kế hoạch còn nhiều giả định có thể dẫn tới nạp trùng, mất dữ liệu, hoặc nạp xong nhưng không lên được tầng dbt/dashboard. Bạn hãy trả lời trực tiếp dưới từng câu hỏi.

### A. Phạm vi dữ liệu cron job

1. Cron job hằng ngày cần crawl nguồn nào?
   - Chỉ Yahoo Finance?
   - Yahoo Finance + World Bank?
   - Có cần FAO/HuggingFace không?
   - Trả lời:- Yahoo Finance + World Bank?, logic tương tự ingest/main.py hiện tại


2. Nếu World Bank là dữ liệu monthly, có thật sự cần chạy mỗi ngày không, hay chỉ chạy theo tháng?
   - Trả lời: chạy theo tháng

3. Danh sách commodity chính thức cho cron job là gì? Hiện `yf_ingest.py` có `coffee`, `rice`, `palm_oil`, `cocoa`, `cotton`, nhưng silver/gold hiện lọc `rice`, `coffee`, `pepper`, `cashew`, `rubber`.
   - Trả lời: tôi không biết, bạn hãy chọn lại bộ commodity cho hợp lí, nếu chọn lại hãy sửa cả dbt và dashboard

4. Có muốn giữ `palm_oil`, `cocoa`, `cotton` trong pipeline gold/dashboard không, hay bỏ khỏi Yahoo để khớp commodity hiện tại?
   - Trả lời:tôi không biết, bạn hãy chọn lại bộ commodity cho hợp lí, nếu chọn lại hãy sửa cả dbt và dashboard

5. Yahoo ticker nào là nguồn chính xác cho từng commodity? Ví dụ `ZR=F` là rough rice futures, không phải giá gạo xuất khẩu Việt Nam hay Thai 5%.
   - Trả lời: tôi không biết, bạn hãy chọn lại bộ commodity cho hợp lí, nếu chọn lại hãy sửa cả dbt và dashboard

6. Giá Yahoo Finance đang là giá futures theo đơn vị hợp đồng, không chắc là USD/kg. Có cần chuẩn hóa đơn vị về `price_usd_per_kg` không, và công thức chuẩn hóa là gì cho từng ticker?
   - Trả lời: tôi không biết, bạn hãy chọn lại bộ commodity cho hợp lí, nếu chọn lại hãy sửa cả dbt và dashboard

7. Bạn muốn dữ liệu Yahoo được xem là dữ liệu "global", "US futures market", hay một region/country cụ thể?
   - Trả lời: tôi không biết, bạn hãy chọn lại bộ commodity cho hợp lí, nếu chọn lại hãy sửa cả dbt và dashboard

### B. Logic incremental và chống trùng

8. Cron nên lấy dữ liệu từ ngày nào?
   - Từ `MAX(price_date) + 1` để tránh trùng?
   - Từ `MAX(price_date)` để tự sửa giá ngày cuối nếu Yahoo điều chỉnh?
   - Từ `today - N days` để backfill các ngày bị trễ?
   - Trả lời: Từ `MAX(price_date) + 1` để tránh trùng?

9. Nên dùng timezone nào để xác định "hôm nay": UTC của GitHub Actions, Asia/Bangkok, hay timezone của thị trường/ticker?
   - Trả lời: Asia/Bangkok

10. Workflow hiện chạy cron `0 17 * * *` UTC, tức 00:00 ngày hôm sau ở Việt Nam. Bạn có muốn giữ lịch này không?
    - Trả lời: sửa lại để crawl theo tháng

11. Nếu Yahoo chưa có dữ liệu ngày mới tại thời điểm cron chạy, script nên:
    - Fail workflow?
    - Log warning và exit code 0?
    - Tự lấy lại vài ngày gần nhất?
    - Trả lời:     - Log warning và exit code 0?


12. Nếu một ticker lỗi nhưng các ticker khác thành công, workflow nên fail toàn bộ hay vẫn commit phần thành công?
    - Trả lời:commit phần thành công

13. Khi dữ liệu đã tồn tại nhưng giá thay đổi, nên `delete + insert` để cập nhật, `insert if not exists`, hay `MERGE/upsert`?
    - Trả lời: delete + insert

14. Unique key chính thức của bảng Yahoo là gì: `(price_date, commodity)`, hay `(price_date, commodity, region, source)`, hay cần thêm `ticker`?
    - Trả lời:tôi không biết, bạn hãy chọn lại bộ commodity cho hợp lí, nếu chọn lại hãy sửa cả dbt và dashboard

15. Có cần lưu cột `ticker`, `open`, `high`, `low`, `volume`, `adj_close` không, hay chỉ lưu close price?
    - Trả lời: close thôi

### C. Schema MotherDuck và dbt

16. Bảng đích cho Yahoo có phải là `bronze.yf_prices_raw` không? Nếu có, schema mong muốn gồm những cột nào?
    - Trả lời:tôi không biết, bạn hãy chọn lại bộ commodity cho hợp lí, nếu chọn lại hãy sửa cả dbt và dashboard

17. Hiện `dbt/models/bronze/sources.yml` chưa khai báo `yf_prices_raw`. Có muốn thêm source này không?
    - Trả lời:tôi không biết, bạn hãy chọn lại bộ commodity cho hợp lí, nếu chọn lại hãy sửa cả dbt và dashboard

18. Hiện `fact_price_daily.sql` chỉ union `silver_fao_prices` và `silver_wb_prices`, chưa có `silver_yf_prices`. Bạn có muốn Yahoo đi vào gold/dashboard không?
    - Trả lời:có

19. Nếu có Yahoo vào gold, có cần tạo `dbt/models/silver/silver_yf_prices.sql` không?
    - Trả lời:tôi không biết, bạn hãy chọn lại bộ commodity cho hợp lí, nếu chọn lại hãy sửa cả dbt và dashboard

20. Nếu Yahoo và World Bank cùng có commodity giống nhau nhưng khác đơn vị/thị trường/tần suất, dashboard nên hiển thị cả hai source hay ưu tiên một source?
    - Trả lời:tôi không biết, bạn hãy chọn lại bộ commodity cho hợp lí, nếu chọn lại hãy sửa cả dbt và dashboard

21. Có cần phân biệt daily futures price và monthly World Bank price trong dashboard/model ML không?
    - Trả lời:tôi không biết, bạn hãy chọn lại bộ commodity cho hợp lí, nếu chọn lại hãy sửa cả dbt và dashboard

22. `dim_date` hiện có đủ ngày tương lai/gần đây để join dữ liệu mới không? Nếu không, cron/dbt có cần tự mở rộng `dim_date` không?
    - Trả lời:tôi không biết, bạn hãy chọn lại bộ commodity cho hợp lí, nếu chọn lại hãy sửa cả dbt và dashboard

### D. Fill forward và chất lượng dữ liệu

23. Có thật sự muốn fill forward cho Thứ 7/Chủ Nhật ở tầng gold không, hay chỉ muốn dashboard/ML xử lý riêng? Fill forward có thể tạo cảm giác như có giá giao dịch thật vào ngày nghỉ.
    - Trả lời:tôi không biết, bạn hãy chọn lại bộ commodity cho hợp lí, nếu chọn lại hãy sửa cả dbt và dashboard

24. Nếu fill forward, có cần thêm cột đánh dấu `is_imputed` hoặc `price_quality` để phân biệt giá thật và giá được điền?
    - Trả lời:tôi không biết, bạn hãy chọn lại bộ commodity cho hợp lí, nếu chọn lại hãy sửa cả dbt và dashboard

25. Fill forward nên áp dụng cho nguồn nào: Yahoo daily, World Bank monthly, FAO, hay tất cả?
    - Trả lời:tôi không biết, bạn hãy chọn lại bộ commodity cho hợp lí, nếu chọn lại hãy sửa cả dbt và dashboard

26. Fill forward tối đa bao nhiêu ngày? Ví dụ chỉ 3 ngày cuối tuần, hay không giới hạn cho các khoảng trống dài?
    - Trả lời:tôi không biết, bạn hãy chọn lại bộ commodity cho hợp lí, nếu chọn lại hãy sửa cả dbt và dashboard

27. Nếu một commodity ngừng trả dữ liệu nhiều ngày, workflow nên cảnh báo theo ngưỡng nào?
    - Trả lời:tôi không biết, bạn hãy chọn lại bộ commodity cho hợp lí, nếu chọn lại hãy sửa cả dbt và dashboard

### E. GitHub Actions và secrets

28. GitHub repository đã có secret `MOTHERDUCK_TOKEN` chưa, và token này có quyền ghi vào database `agri_dwh` không?
    - Trả lời:có

29. Có muốn dùng env `MOTHERDUCK_DATABASE` hay `MOTHERDUCK_DB` làm tên database chuẩn? Repo hiện có cả logic đọc `MOTHERDUCK_DATABASE` trong Python và `MOTHERDUCK_DB` trong dbt profile.
    - Trả lời: không

30. Có cần cài thêm dependency cho dbt trong GitHub Actions không? `ingest/requirements.txt` hiện chưa thấy `dbt-duckdb`.
    - Trả lời: có

31. Khi thêm `dbt build`, workflow nên chạy từ thư mục nào và dùng `--profiles-dir` nào?
    - Trả lời:tôi không biết, bạn hãy chọn lại bộ commodity cho hợp lí, nếu chọn lại hãy sửa cả dbt và dashboard

32. Nếu `dbt build` fail sau khi ingest đã ghi bronze thành công, bạn muốn xử lý thế nào? Giữ dữ liệu bronze và báo lỗi, hay rollback ingest?
    - Trả lời:Giữ dữ liệu bronze và báo lỗi

33. Có cần upload log/artifact cả khi thành công để audit dữ liệu vừa nạp không?
    - Trả lời:

### F. Cách tổ chức code

34. Có chắc muốn tạo `ingest/daily_cron.py` mới hoàn toàn, hay nên tái dùng helper hiện có trong `ingest/utils.py` như `motherduck_connection`, `retry`, `write_dataframe`?
    - Trả lời:

35. Có muốn refactor nhẹ `yf_ingest.py` để dùng chung function fetch/transform với `daily_cron.py`, hay giữ nguyên batch file và chấp nhận duplicate code?
    - Trả lời:

36. File batch hiện tại `yf_ingest.py` đang dùng `duckdb.connect("md:agri_dwh")` trực tiếp, còn `utils.py` đã hỗ trợ token/env. Có muốn đồng bộ cách connect không?
    - Trả lời:

37. Có cần chế độ dry-run cho cron để test trên GitHub Actions mà không ghi database không?
    - Trả lời:

38. Có cần tham số CLI như `--start-date`, `--end-date`, `--tickers`, `--lookback-days` để dễ chạy lại thủ công không?
    - Trả lời:

### G. Kiểm thử và tiêu chí hoàn thành

39. Bạn muốn tôi viết test tự động cho phần transform/upsert không, hay chỉ chạy compile/build thủ công?
    - Trả lời:

40. Tiêu chí "xong" là gì?
    - Workflow GitHub Actions chạy xanh?
    - Bronze có dòng mới?
    - Gold/dashboard có dữ liệu mới?
    - Cả ba điều trên?
    - Trả lời:    - Cả ba điều trên?


41. Có cần tôi cập nhật README/runbook cách set GitHub secret, chạy lại workflow, và debug cron fail không?
    - Trả lời: CÓ, ĐẶC BIỆT CÓ

42. Có môi trường staging/test database để thử cron trước khi ghi vào MotherDuck production không?
    - Trả lời:KHÔNG
