function getLocation() {

    const status = document.getElementById("locationStatus");
    const latInput = document.getElementById("lat");
    const lonInput = document.getElementById("lon");

    if (!navigator.geolocation) {

        status.innerHTML = `
            <div class="d-flex align-items-center gap-2">
                <span>⚠️</span>
                <span>Browser tidak mendukung Geolocation.</span>
            </div>
            <small>Silakan isi latitude dan longitude secara manual.</small>
        `;

        status.className = "gps-box gps-warning";
        return;
    }

    status.innerHTML = `
        <div class="d-flex align-items-center gap-2">
            <div class="spinner-border spinner-border-sm text-success"
                 role="status">
            </div>

            <span>Mengambil lokasi GPS...</span>
        </div>
    `;

    status.className = "gps-box gps-info";

    navigator.geolocation.getCurrentPosition(

        function(position) {

            latInput.value =
                position.coords.latitude.toFixed(7);

            lonInput.value =
                position.coords.longitude.toFixed(7);

            status.innerHTML = `
                <div class="d-flex align-items-center gap-2">
                    <span>✅</span>
                    <span>Lokasi berhasil diperoleh</span>
                </div>

                <small>
                    Latitude : ${latInput.value}
                    <br>
                    Longitude : ${lonInput.value}
                </small>
            `;

            status.className = "gps-box gps-success";
        },

        function(error) {

            let message =
                "Izin lokasi ditolak atau GPS tidak tersedia.";

            switch(error.code){

                case error.PERMISSION_DENIED:
                    message =
                        "Izin lokasi ditolak oleh pengguna.";
                    break;

                case error.POSITION_UNAVAILABLE:
                    message =
                        "Informasi lokasi tidak tersedia.";
                    break;

                case error.TIMEOUT:
                    message =
                        "Waktu pengambilan lokasi habis.";
                    break;
            }

            status.innerHTML = `
                <div class="d-flex align-items-center gap-2">
                    <span>❌</span>
                    <span>${message}</span>
                </div>

                <small>
                    Isi latitude dan longitude secara manual
                    atau gunakan HTTPS/localhost.
                </small>
            `;

            status.className = "gps-box gps-warning";
        },

        {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 0
        }

    );
}