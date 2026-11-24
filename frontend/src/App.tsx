import { useCallback, useEffect, useState } from "react";
import { auth } from "./api";
import Chat from "./Chat";
import { IconList, IconLogout, IconPlane, IconSparkle } from "./icons";
import Login from "./Login";
import MemoryPanel from "./MemoryPanel";
import OrderPage from "./OrderPage";
import OrdersPage from "./OrdersPage";

function useHashRoute(): string {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const on = () => setHash(window.location.hash);
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return hash;
}

export default function App() {
  const [user, setUser] = useState<string | null>(auth.user());
  const [showMemory, setShowMemory] = useState(false);
  const hash = useHashRoute();

  const lost = useCallback(() => {
    auth.clear();
    setUser(null);
  }, []);

  if (!user || !auth.token()) {
    return <Login onDone={() => setUser(auth.user())} />;
  }

  const order = /^#\/orders\/([A-Za-z0-9_-]+)$/.exec(hash);
  const onOrders = hash === "#/orders" || order !== null;
  return (
    <div className="shell">
      <header className="top">
        <div className="top-inner">
          <a href="#/" className="brand" aria-label="Trợ lý Chuyến đi, về trang trò chuyện">
            <span className="logo" aria-hidden="true">
              <IconPlane size={18} />
            </span>
            <span className="brand-text">Trợ lý Chuyến đi</span>
          </a>
          <nav className="nav" aria-label="Điều hướng chính">
            <a href="#/" aria-current={!onOrders ? "page" : undefined}>
              <IconSparkle size={16} /> Trò chuyện
            </a>
            <a href="#/orders" aria-current={onOrders ? "page" : undefined}>
              <IconList size={16} /> Đơn của tôi
            </a>
          </nav>
          <div className="userbox">
            <span className="avatar-sm" aria-hidden="true">
              {user.slice(0, 1)}
            </span>
            <span className="who">{user}</span>
            <button className="icon-btn" onClick={lost} aria-label="Đăng xuất" title="Đăng xuất">
              <IconLogout size={18} />
            </button>
          </div>
        </div>
      </header>
      {order ? (
        <OrderPage orderId={order[1]} onAuthLost={lost} />
      ) : hash === "#/orders" ? (
        <OrdersPage onAuthLost={lost} />
      ) : (
        <Chat onAuthLost={lost} onOpenMemory={() => setShowMemory(true)} />
      )}
      {showMemory && <MemoryPanel onClose={() => setShowMemory(false)} onAuthLost={lost} />}
    </div>
  );
}