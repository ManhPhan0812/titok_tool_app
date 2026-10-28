# HaizFlow 1.0.4 — bản fork của ManhPhan0812

Bản fork dựa trên HaizFlow 1.0.4 của Mạch Hồng Hải, kèm các thay đổi riêng trong repository `ManhPhan0812/titok_tool_app`.

## Cài đặt

[Tải HaizFlow-1.0.4-Setup.exe](https://github.com/ManhPhan0812/titok_tool_app/releases/download/v1.0.4/HaizFlow-1.0.4-Setup.exe). Người cài mới chỉ cần bộ cài; các tệp Core ZIP và manifest dành cho cập nhật trong app.

Windows 10/11 x64. Bộ cài chưa ký Authenticode; Windows có thể cảnh báo hoặc chặn theo chính sách.

## Thay đổi riêng

- Chế độ Tự động có bốn lựa chọn nội dung xuất: phụ đề và lồng tiếng, chỉ phụ đề, chỉ lồng tiếng, hoặc không phụ đề và không lồng tiếng. Khi tắt lồng tiếng, giữ âm thanh gốc theo mức âm lượng đã chọn. Phụ đề đã có sẵn trong hình ảnh được xử lý bằng tùy chọn che phụ đề riêng.
- Sửa môi trường chạy bộ xử lý khi mở source bằng `Chay-HaizFlow.bat`.
- Giải phóng video preview trước khi xóa dự án để tránh file còn bị khóa.
- Khôi phục SDK VieNeu khi thư mục runtime cũ bị từ chối truy cập, có kiểm tra toàn vẹn và giữ bản sao dự phòng.
- Chuyển kênh cập nhật Core và bộ cài sang repository của bản fork. Các gói tài nguyên được ghim tiếp tục sử dụng URL trong catalog.
- Loại trừ dữ liệu runtime, cấu hình cá nhân, model và cache khỏi mã nguồn phát hành.

## Chuyển từ bản gốc hoặc bản build cũ

Cài bộ Setup này để chuyển kênh cập nhật sang bản fork. EXE cũ vẫn giữ địa chỉ cập nhật được nhúng khi build. Hai bản cùng số `1.0.4` không tự cập nhật cho nhau; các release tiếp theo của bản fork cần tăng số phiên bản.

Lưu công việc, đóng app và giữ bản sao dự án trước khi nâng cấp. Không xóa `runtime` hoặc thư mục dự án. Full Core được cung cấp cho cập nhật; bản phát hành đầu tiên của fork không có Delta từ các bản gốc.

## Giấy phép và nguồn thư viện

Giữ nguyên thông báo tác giả và giấy phép HaizFlow Source-Available 1.0 cùng giấy phép của các thành phần. Đây là bản fork, không phải bản phát hành chính thức của tác giả gốc. Điều kiện riêng của model, gồm checkpoint OmniVoice phi thương mại, vẫn áp dụng.

[Nguồn thư viện tương ứng](https://github.com/ManhPhan0812/titok_tool_app/releases/download/v1.0.4/HaizFlow-1.0.4-ThirdPartySources.zip) được cung cấp cùng release.
