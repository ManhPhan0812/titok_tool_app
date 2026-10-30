# HaizFlow 1.0.5 — hỗ trợ máy cấu hình thấp

- Cho phép xử lý trên máy RAM lắp đặt từ 8 GB, Windows sử dụng được ít nhất 6 GiB; khuyên dùng từ 16 GB.
- Máy dưới 12 GiB RAM dùng được không nạp model đón trước. Gói CPU 18 dùng Whisper batch 1, tối đa 2 luồng và giải phóng worker dịch sau 15 giây rảnh.
- Nhận diện GPU cũ không tương thích bộ PyTorch 2.8/CUDA 12.8, kể cả Quadro K1000M khi driver không báo kiến trúc. Tự chuyển cài đặt GPU không phù hợp về CPU khi khởi động và hướng dẫn chọn model CPU trong Gói tài nguyên.
- Giữ kiểm tra RAM trống và bộ nhớ Windows còn cấp phát trước các bước AI nặng. Cấu hình tối thiểu không bảo đảm mọi model đều chạy được khi thiếu bộ nhớ.

## Cập nhật từ bản fork 1.0.4

1. Mở **Cài đặt → Chung → Kiểm tra cập nhật**, cài 1.0.5 và khởi động lại ứng dụng.
2. Mở **Cài đặt → Gói tài nguyên**, cập nhật bộ xử lý CPU khi ứng dụng yêu cầu. Nếu chưa cài, cài Whisper Small và HY-MT2 CPU Q4 để nhận gói CPU mới cùng model cần dùng.
3. Với Quadro K1000M 2 GB, chọn **CPU**, **Whisper Small CPU**, **HY-MT2 CPU Q4**; giọng VieNeu CPU cho tiếng Việt hoặc Edge TTS qua Internet. Bắt đầu với tách giọng tắt nếu không cần.

K1000M có compute capability 3.0, không chạy được bộ CUDA hiện tại. Bản này hỗ trợ máy đó qua CPU, không bật tăng tốc AI bằng K1000M. Chưa benchmark trực tiếp trên máy K1000M.

Model và dự án đã lưu được giữ nguyên. Bản cài vẫn chưa có chữ ký số. Máy còn dùng bản gốc hoặc chưa chuyển sang kênh fork cần cài Setup từ release này để nhận các cập nhật tiếp theo của `ManhPhan0812/titok_tool_app`.
