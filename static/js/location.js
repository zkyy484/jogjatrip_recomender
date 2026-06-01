function getLocation() {
  const status = document.getElementById('locationStatus');
  const latInput = document.getElementById('lat');
  const lonInput = document.getElementById('lon');

  if (!navigator.geolocation) {
    status.innerHTML = 'Browser tidak mendukung Geolocation. Isi latitude dan longitude manual.';
    status.className = 'gps-box mt-3 gps-warning';
    return;
  }

  status.innerHTML = 'Mengambil lokasi GPS user...';
  status.className = 'gps-box mt-3 gps-info';

  navigator.geolocation.getCurrentPosition(
    (position) => {
      latInput.value = position.coords.latitude.toFixed(7);
      lonInput.value = position.coords.longitude.toFixed(7);
      status.innerHTML = `Lokasi berhasil diambil: ${latInput.value}, ${lonInput.value}`;
      status.className = 'gps-box mt-3 gps-success';
    },
    () => {
      status.innerHTML = 'Izin lokasi ditolak/gagal. Isi latitude dan longitude manual, atau jalankan di localhost/HTTPS.';
      status.className = 'gps-box mt-3 gps-warning';
    },
    {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 0,
    }
  );
}
