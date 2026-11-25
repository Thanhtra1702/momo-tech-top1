const cinemas = [
  { name: "CGV", url: "https://www.cgv.vn/default/movies/now-showing.html" },
  { name: "Galaxy Cinema", url: "https://www.galaxycine.vn/phim-dang-chieu/" },
  { name: "Lotte Cinema", url: "https://www.lottecinemavn.com/LCHS/Contents/Movie/Movie-List.aspx" },
];

export default function CinemaPage() {
  return <main className="page live-events">
    <h1>Phim tại rạp</h1>
    <p className="muted">Tên phim và suất chiếu trong danh mục mẫu không phản ánh lịch của rạp. Hãy xem trực tiếp danh sách đang chiếu, chọn rạp và ngày trên website chính thức trước khi đặt.</p>
    <ul className="live-list">
      {cinemas.map((cinema) => <li className="panel-card" key={cinema.name}>
        <h2>{cinema.name}</h2>
        <p>Phim, suất chiếu, giá và số ghế do rạp cập nhật.</p>
        <a className="btn-primary link" href={cinema.url} target="_blank" rel="noopener noreferrer">Mở {cinema.name}</a>
      </li>)}
    </ul>
    <p className="notice">Ứng dụng chưa có quyền truy cập API đặt vé của các rạp, nên không hiển thị giá, ghế trống hoặc tạo đơn phim thật.</p>
  </main>;
}
