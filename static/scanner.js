// let scannedQRCodes = [];
// let html5QrcodeScanner;
// let isScanning = false;

// // ✅ courseId comes from scanner.html (don't redeclare here!)

// function updateProgress() {
//   const progress = (scannedQRCodes.length / 4) * 100;
//   document.getElementById('progressFill').style.width = progress + '%';
//   document.getElementById('progressText').textContent =
//     `${scannedQRCodes.length} of 4 codes scanned`;
// }

// function updateScannedList() {
//   const resultDiv = document.getElementById('result');
//   updateProgress();

//   if (scannedQRCodes.length === 0) {
//     resultDiv.innerHTML = '<div class="no-codes">No QR codes scanned yet.</div>';
//   } else {
//     resultDiv.innerHTML =
//       `<div class="no-codes">${scannedQRCodes.length} QR code${scannedQRCodes.length > 1 ? 's' : ''} scanned successfully! ✅</div>`;
//   }
// }

// function startScanning() {
//   if (isScanning) return;

//   isScanning = true;
//   const startBtn = document.getElementById('startBtn');
//   const scannerStatus = document.getElementById('scannerStatus');
//   const reader = document.getElementById('reader');

//   startBtn.disabled = true;
//   startBtn.textContent = '🔄 Starting Camera...';
//   scannerStatus.textContent = '📷 Initializing camera...';

//   reader.classList.remove('hidden');

//   html5QrcodeScanner = new Html5QrcodeScanner("reader", {
//     fps: 10,
//     qrbox: { width: 250, height: 250 },
//     aspectRatio: 1.0
//   });

//   html5QrcodeScanner.render(onScanSuccess, onScanError);

//   startBtn.style.display = 'none';
//   scannerStatus.textContent = '📱 Point your camera at a QR code to scan';
// }

// function onScanSuccess(decodedText, decodedResult) {
//   if (!scannedQRCodes.includes(decodedText)) {
//     scannedQRCodes.push(decodedText);
//     updateScannedList();

//     if (scannedQRCodes.length === 4) {
//       html5QrcodeScanner.clear();
//       document.getElementById('scannerStatus').innerHTML =
//         '🎉 All codes scanned! Sending to backend...';

//       fetch('/save_qr_data', {
//         method: 'POST',
//         headers: { 'Content-Type': 'application/json' },
//         body: JSON.stringify({ course_id: courseId, qr_codes: scannedQRCodes })
//       })
//         .then(response => response.text())
//         .then(html => {
//           document.open();
//           document.write(html);
//           document.close();
//         })
//         .catch(() => {
//           document.getElementById('result').innerHTML +=
//             '<div class="success-message" style="background: linear-gradient(135deg, #ef4444, #dc2626);">❌ Error sending QR codes</div>';
//         });
//     }
//   }
// }

// function onScanError(errorMessage) {
//   // Ignore scanning errors (normal when no QR code detected)
// }

// window.onload = function () {
//   updateScannedList();
// };


let scannedQRCodes = [];
let html5QrcodeScanner;
let isScanning = false;

function updateProgress() {
  const progress = (scannedQRCodes.length / 4) * 100;
  document.getElementById('progressFill').style.width = progress + '%';
  document.getElementById('progressText').textContent = `${scannedQRCodes.length} of 4 codes scanned`;
}

function updateScannedList() {
  const resultDiv = document.getElementById('result');
  updateProgress();

  if (scannedQRCodes.length === 0) {
    resultDiv.innerHTML = '<div class="no-codes">No QR codes scanned yet.</div>';
  } else {
    // Show count instead of actual QR codes
    resultDiv.innerHTML = `<div class="no-codes">${scannedQRCodes.length} QR code${scannedQRCodes.length > 1 ? 's' : ''} scanned successfully! ✅</div>`;
  }
}

function startScanning() {
  if (isScanning) return;

  isScanning = true;
  const startBtn = document.getElementById('startBtn');
  const scannerStatus = document.getElementById('scannerStatus');
  const reader = document.getElementById('reader');

  startBtn.disabled = true;
  startBtn.textContent = '🔄 Starting Camera...';
  scannerStatus.textContent = '📷 Initializing camera...';

  reader.classList.remove('hidden');

  html5QrcodeScanner = new Html5QrcodeScanner(
    "reader",
    {
      fps: 10,
      qrbox: { width: 250, height: 250 },
      aspectRatio: 1.0
    }
  );

  html5QrcodeScanner.render(onScanSuccess, onScanError).then(() => {
    startBtn.style.display = 'none';
    scannerStatus.textContent = '📱 Point your camera at a QR code to scan';
  }).catch((err) => {
    startBtn.disabled = false;
    startBtn.textContent = '🚀 Start Scanning';
    scannerStatus.textContent = '❌ Camera access denied. Please allow camera permissions and try again.';
    reader.classList.add('hidden');
    isScanning = false;
  });
}

function onScanSuccess(decodedText, decodedResult) {
  if (!scannedQRCodes.includes(decodedText)) {
    scannedQRCodes.push(decodedText);
    updateScannedList();

    if (scannedQRCodes.length === 4) {
      html5QrcodeScanner.clear();
      document.getElementById('scannerStatus').innerHTML = '🎉 All codes scanned! Saving...';

      // Send all 4 codes to backend to save in contain.textfile
      fetch('/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ data: scannedQRCodes.join('\n') })
      }).then(() => {
        document.getElementById('result').innerHTML +=
          '<div class="success-message">🎉 Successfully saved to contain.textfile!</div>';
        document.getElementById('scannerStatus').innerHTML = '✅ Scanning completed successfully';
      }).catch(() => {
        document.getElementById('result').innerHTML +=
          '<div class="success-message" style="background: linear-gradient(135deg, #ef4444, #dc2626);">❌ Error saving to file</div>';
      });
    }
  }
}

function onScanError(errorMessage) {
  // Handle scan error silently - this is normal when no QR code is in view
}

window.onload = function() {
  updateScannedList();
};