"""Ngữ cảnh TLS cho urllib. Python của python.org trên macOS không có sẵn chứng chỉ gốc, nên cần bộ của certifi
(build_macos.sh cài certifi và PyInstaller đóng gói cùng app). Windows dùng kho chứng chỉ hệ thống: không đổi."""
import ssl


def context():
    try:
        import certifi
    except ImportError:
        return None  # None = urllib dùng mặc định
    return ssl.create_default_context(cafile=certifi.where())
