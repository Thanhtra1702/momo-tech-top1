import { Component, ReactNode } from "react";

interface State {
  failed: boolean;
}

/** Bắt lỗi hiển thị bất ngờ để người dùng thấy hướng dẫn thay vì trang trắng. */
export default class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error) {
    console.error("UI error:", error.message);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <main className="page" role="alert">
        <h1>Có lỗi xảy ra</h1>
        <p>Giao diện gặp sự cố ngoài ý muốn. Dữ liệu cuộc trò chuyện của bạn đã được lưu trên máy chủ.</p>
        <button className="btn-primary" onClick={() => window.location.reload()}>
          Tải lại trang
        </button>
      </main>
    );
  }
}
