# HaizFlow 1.0.6 — Whisper cho GPU cũ

- Thêm lựa chọn **Whisper Base · GPU cũ (DirectCompute)** cho nhận dạng giọng nói
  bằng Direct3D 11, dành cho card như Quadro K1000M khi driver tương thích.
- Giữ bộ xử lý chung ở **CPU**. Nhận diện ngôn ngữ, căn thời gian, dịch và giọng
  đọc vẫn dùng CPU. Bản này chưa có chế độ hỗn hợp tự động cho toàn bộ tác vụ.
- Gói tài nguyên tải CLI và model Base đã ghim SHA-256 từ nhà cung cấp; tái sử
  dụng bộ CPU 18 và Whisper Small đã cài cho phần nhận diện ngôn ngữ/căn thời gian.
- Chọn đúng adapter NVIDIA trên laptop hai GPU, kiểm tra đầu ra và hỗ trợ tiếp
  tục sau khi tạm dừng. Không xuất SRT thô của GPU thành kết quả đã căn thời gian.

## Cách dùng trên K1000M

1. Cập nhật ứng dụng lên **1.0.6** rồi khởi động lại.
2. **Cài đặt → Chung → Bộ xử lý → CPU → Áp dụng**.
3. **Gói tài nguyên → Whisper Base · GPU cũ (DirectCompute) → Cài đặt**.
4. Trong dự án, chọn model nhận dạng **Whisper Base · GPU cũ (DirectCompute)**,
   **HY-MT2 CPU · Q4** và giọng CPU.

Whisper Base nhẹ hơn Small và độ chính xác có thể thấp hơn. Các lựa chọn model
cũ không bị tự thay đổi. Whisper Turbo, HY-MT2 GPU đầy đủ và giọng GPU vẫn cần
bộ CUDA tương thích; bản này không làm mọi model GPU chạy được trên K1000M.
Đã kiểm tra DirectCompute trên Intel UHD 630 và luồng CPU 18; chưa benchmark
trực tiếp K1000M. Không bảo đảm nhanh hơn CPU cho video ngắn.

Ứng dụng vẫn yêu cầu ít nhất 8 GiB RAM lắp đặt, 6 GiB Windows sử dụng được và
đủ RAM/bộ nhớ cấp phát ở từng bước. Bộ cài chưa có chữ ký số.

Xem [hướng dẫn chi tiết](legacy-gpu.md).
