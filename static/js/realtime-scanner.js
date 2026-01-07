/**
 * Void Tax System - Real-time Car Plate Scanner
 * Handles webcam capture and continuous scanning
 */

class RealtimeScanner {
    constructor(options = {}) {
        this.videoElement = document.getElementById('webcam');
        this.canvasElement = document.getElementById('canvas');
        this.statusElement = document.getElementById('status');
        this.resultsContainer = document.getElementById('results');
        this.finesContainer = document.getElementById('finesResults');
        this.statsElement = document.getElementById('stats');
        
        this.scanInterval = options.scanInterval || 500; // ms
        this.isScanning = false;
        this.stream = null;
        this.intervalId = null;
        
        // Statistics
        this.totalScans = 0;
        this.platesDetected = 0;
        this.finesIssued = 0;
        this.cachedResults = 0;
        this.totalFineAmount = 0;
        
        // Recent results (for display)
        this.recentResults = [];
        this.maxRecentResults = 20;
        
        // Fines list
        this.finesList = [];
        this.maxFines = 50;
        
        this.init();
    }
    
    async init() {
        console.log('🚀 RealtimeScanner initializing...');
        console.log('🔍 finesContainer element:', this.finesContainer);
        console.log('🔍 resultsContainer element:', this.resultsContainer);
        
        // Set up event listeners
        document.getElementById('startBtn').addEventListener('click', () => this.start());
        document.getElementById('stopBtn').addEventListener('click', () => this.stop());
        
        this.updateStatus('Ready', 'idle');
        this.updateStats();
        
        // Load existing fines
        this.loadFines();
    }
    
    async loadFines() {
        console.log('📥 loadFines() called, finesContainer:', this.finesContainer);
        
        // Show loading indicator
        if (this.finesContainer) {
            this.finesContainer.innerHTML = '<p class="no-results">Loading fines...</p>';
        }
        
        try {
            const response = await fetch('/api/fines?limit=50');
            console.log('📥 Fines API response status:', response.status);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const fines = await response.json();
            console.log('📥 Fines loaded:', fines.length, 'items');
            console.log('📥 Raw fines data:', JSON.stringify(fines.slice(0, 2)));
            
            this.finesList = fines.map(f => ({
                ...f,
                issued_at: new Date(f.issued_at)
            }));
            this.totalFineAmount = this.finesList.reduce((sum, f) => sum + f.fine_amount, 0);
            this.finesIssued = this.finesList.length;
            console.log('📥 Total fine amount:', this.totalFineAmount, ', count:', this.finesIssued);
            
            this.renderFines();
            this.updateStats();
        } catch (error) {
            console.error('❌ Error loading fines:', error);
            if (this.finesContainer) {
                this.finesContainer.innerHTML = `<p class="no-results" style="color: red;">Error loading fines: ${error.message}</p>`;
            }
        }
    }
    
    async start() {
        try {
            this.updateStatus('Requesting camera access...', 'loading');
            
            // Request webcam access
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    width: { ideal: 1280 },
                    height: { ideal: 720 },
                    facingMode: 'environment' // Prefer rear camera on mobile
                }
            });
            
            this.videoElement.srcObject = this.stream;
            await this.videoElement.play();
            
            // Set canvas size to match video
            this.canvasElement.width = this.videoElement.videoWidth;
            this.canvasElement.height = this.videoElement.videoHeight;
            
            this.isScanning = true;
            this.updateStatus('Scanning...', 'active');
            
            // Start continuous scanning
            this.intervalId = setInterval(() => this.scanFrame(), this.scanInterval);
            
            // Update UI
            document.getElementById('startBtn').disabled = true;
            document.getElementById('stopBtn').disabled = false;
            
        } catch (error) {
            console.error('Camera access error:', error);
            this.updateStatus(`Camera error: ${error.message}`, 'error');
        }
    }
    
    stop() {
        this.isScanning = false;
        
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }
        
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }
        
        this.videoElement.srcObject = null;
        this.updateStatus('Stopped', 'idle');
        
        // Update UI
        document.getElementById('startBtn').disabled = false;
        document.getElementById('stopBtn').disabled = true;
    }
    
    async scanFrame() {
        if (!this.isScanning) return;
        
        try {
            // Capture frame to canvas
            const ctx = this.canvasElement.getContext('2d');
            ctx.drawImage(this.videoElement, 0, 0);
            
            // Convert to base64
            const imageData = this.canvasElement.toDataURL('image/jpeg', 0.8);
            
            // If debug mode is enabled, also get debug view
            if (window.DEBUG_MODE) {
                this.updateDebugView(imageData);
            }
            
            // Send to backend
            const response = await fetch('/api/scan-frame-base64', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ image: imageData })
            });
            
            const result = await response.json();
            this.totalScans++;
            
            if (result.success && result.plates_detected > 0) {
                this.processResults(result);
            }
            
            this.updateStats();
            
        } catch (error) {
            console.error('Scan error:', error);
        }
    }
    
    async updateDebugView(imageData) {
        try {
            const response = await fetch('/api/debug-detection', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ image: imageData })
            });
            
            const result = await response.json();
            
            // Update debug image
            const debugImage = document.getElementById('debugImage');
            if (debugImage && result.debug_image) {
                debugImage.src = result.debug_image;
            }
            
            // Update region count
            const debugRegions = document.getElementById('debugRegions');
            if (debugRegions) {
                debugRegions.textContent = result.regions_detected;
            }
            
            // Update region list
            const debugRegionList = document.getElementById('debugRegionList');
            if (debugRegionList && result.regions) {
                debugRegionList.innerHTML = result.regions.map(r => `
                    <div class="region">
                        🎯 Plate ${r.id}: ${r.width}×${r.height}px - confidence: ${(r.confidence * 100).toFixed(0)}%
                    </div>
                `).join('');
            }
        } catch (error) {
            console.error('Debug view error:', error);
        }
    }
    
    processResults(result) {
        console.log('📊 Processing results:', result.results.length, 'plates');
        
        for (const scanResult of result.results) {
            this.platesDetected++;
            console.log(`🚗 Plate: ${scanResult.plate_number}, Confidence: ${(scanResult.confidence * 100).toFixed(1)}%, Fine issued: ${scanResult.fine_issued}`);
            
            if (scanResult.cached) {
                this.cachedResults++;
            }
            
            if (scanResult.fine_issued) {
                console.log(`💰 FINE ISSUED: ${scanResult.plate_number} - RM ${scanResult.fine_amount}`);
                this.finesIssued++;
                this.totalFineAmount += scanResult.fine_amount || 0;
                
                // Add to fines list
                this.addFine(scanResult);
            }
            
            // Add to recent results
            this.addResult(scanResult);
        }
    }
    
    addFine(scanResult) {
        console.log('📝 Adding fine to list:', scanResult);
        
        const fine = {
            plate_number: scanResult.plate_number,
            fine_amount: scanResult.fine_amount,
            fine_type: this.getFineType(scanResult),
            owner_name: scanResult.vehicle_status?.owner_name || 'Unknown',
            issued_at: new Date()
        };
        
        console.log('📝 Fine object:', fine);
        
        // Add to front of array
        this.finesList.unshift(fine);
        
        console.log('📝 Fines list now has', this.finesList.length, 'items');
        
        // Trim to max size
        if (this.finesList.length > this.maxFines) {
            this.finesList.pop();
        }
        
        // Update display
        this.renderFines();
    }
    
    getFineType(result) {
        if (!result.vehicle_status) return 'unknown';
        const status = result.vehicle_status;
        if (!status.road_tax_valid && !status.insurance_valid) return 'both';
        if (!status.road_tax_valid) return 'road_tax';
        if (!status.insurance_valid) return 'insurance';
        return 'unknown';
    }
    
    getFineTypeLabel(type) {
        switch(type) {
            case 'road_tax': return 'Road Tax Expired';
            case 'insurance': return 'Insurance Expired';
            case 'both': return 'Tax & Insurance';
            default: return 'Violation';
        }
    }
    
    renderFines() {
        console.log('🎨 renderFines called, container exists:', !!this.finesContainer, ', fines count:', this.finesList.length);
        console.log('🎨 First fine:', this.finesList[0]);
        
        if (!this.finesContainer) {
            console.error('❌ finesContainer not found! Looking for element #finesResults');
            // Try to find it again
            this.finesContainer = document.getElementById('finesResults');
            console.log('🔍 Re-searched for finesContainer:', !!this.finesContainer);
            if (!this.finesContainer) return;
        }
        
        if (this.finesList.length === 0) {
            console.log('🎨 No fines to display');
            this.finesContainer.innerHTML = '<p class="no-results">No fines issued yet...</p>';
        } else {
            console.log('🎨 Rendering', this.finesList.length, 'fines');
            const html = this.finesList.map(fine => {
                console.log('🎨 Rendering fine:', fine.plate_number, fine.fine_amount);
                const timeStr = fine.issued_at.toLocaleTimeString();
                const dateStr = fine.issued_at.toLocaleDateString();
                
                return `
                    <div class="fine-card">
                        <div class="fine-header">
                            <span class="plate">${fine.plate_number}</span>
                            <span class="amount">RM ${fine.fine_amount.toFixed(2)}</span>
                        </div>
                        <div class="fine-details">
                            ${dateStr} at ${timeStr}
                        </div>
                        <span class="fine-type ${fine.fine_type}">${this.getFineTypeLabel(fine.fine_type)}</span>
                        ${fine.owner_name ? `<div class="owner">👤 ${fine.owner_name}</div>` : ''}
                    </div>
                `;
            }).join('');
            
            console.log('🎨 Setting innerHTML, length:', html.length);
            this.finesContainer.innerHTML = html;
            console.log('🎨 innerHTML set, container now has', this.finesContainer.children.length, 'children');
        }
        
        // Update total
        const totalElement = document.getElementById('totalFines');
        console.log('🎨 totalElement found:', !!totalElement, ', total amount:', this.totalFineAmount);
        if (totalElement) {
            totalElement.textContent = `RM ${this.totalFineAmount.toFixed(2)}`;
        }
    }
    
    addResult(scanResult) {
        // Create result entry
        const entry = {
            timestamp: new Date(),
            ...scanResult
        };
        
        // Add to front of array
        this.recentResults.unshift(entry);
        
        // Trim to max size
        if (this.recentResults.length > this.maxRecentResults) {
            this.recentResults.pop();
        }
        
        // Update display
        this.renderResults();
        
        // Play sound for new detections (non-cached)
        if (!scanResult.cached) {
            this.playNotification(scanResult);
        }
    }
    
    renderResults() {
        if (!this.resultsContainer) return;
        
        const html = this.recentResults.map(result => {
            const statusClass = this.getStatusClass(result);
            const statusText = this.getStatusText(result);
            const timeStr = result.timestamp.toLocaleTimeString();
            
            return `
                <div class="result-card ${statusClass} ${result.cached ? 'cached' : 'new'}">
                    <div class="result-header">
                        <span class="plate-number">${result.plate_number}</span>
                        <span class="confidence">${(result.confidence * 100).toFixed(0)}%</span>
                    </div>
                    <div class="result-status">
                        <span class="status-badge ${statusClass}">${statusText}</span>
                        ${result.cached ? '<span class="cached-badge">CACHED</span>' : ''}
                    </div>
                    ${result.fine_issued ? `
                        <div class="fine-info">
                            <span class="fine-amount">Fine: RM ${result.fine_amount.toFixed(2)}</span>
                        </div>
                    ` : ''}
                    <div class="result-time">${timeStr}</div>
                </div>
            `;
        }).join('');
        
        this.resultsContainer.innerHTML = html || '<p class="no-results">No plates detected yet...</p>';
    }
    
    getStatusClass(result) {
        if (result.error) return 'error';
        if (!result.vehicle_status) return 'unknown';
        
        const status = result.vehicle_status;
        if (status.road_tax_valid && status.insurance_valid) return 'compliant';
        if (!status.road_tax_valid && !status.insurance_valid) return 'both-expired';
        if (!status.road_tax_valid) return 'tax-expired';
        if (!status.insurance_valid) return 'insurance-expired';
        return 'unknown';
    }
    
    getStatusText(result) {
        if (result.error) return 'Error';
        if (!result.vehicle_status) return 'Unknown';
        
        const status = result.vehicle_status;
        if (status.road_tax_valid && status.insurance_valid) return 'Compliant';
        if (!status.road_tax_valid && !status.insurance_valid) return 'Tax & Insurance Expired';
        if (!status.road_tax_valid) return 'Road Tax Expired';
        if (!status.insurance_valid) return 'Insurance Expired';
        return 'Unknown';
    }
    
    playNotification(result) {
        // Create audio context for notification sounds
        try {
            const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = audioCtx.createOscillator();
            const gainNode = audioCtx.createGain();
            
            oscillator.connect(gainNode);
            gainNode.connect(audioCtx.destination);
            
            // Different sounds for different statuses
            if (result.fine_issued) {
                // Alert sound for fines
                oscillator.frequency.value = 440;
                oscillator.type = 'square';
                gainNode.gain.value = 0.1;
            } else {
                // Soft beep for compliant
                oscillator.frequency.value = 800;
                oscillator.type = 'sine';
                gainNode.gain.value = 0.05;
            }
            
            oscillator.start();
            setTimeout(() => {
                oscillator.stop();
            }, 150);
        } catch (e) {
            // Audio not supported
        }
    }
    
    updateStatus(message, state) {
        if (!this.statusElement) return;
        
        this.statusElement.textContent = message;
        this.statusElement.className = `status ${state}`;
    }
    
    updateStats() {
        if (!this.statsElement) return;
        
        this.statsElement.innerHTML = `
            <div class="stat">
                <span class="stat-value">${this.totalScans}</span>
                <span class="stat-label">Scans</span>
            </div>
            <div class="stat">
                <span class="stat-value">${this.platesDetected}</span>
                <span class="stat-label">Plates</span>
            </div>
            <div class="stat">
                <span class="stat-value">${this.finesIssued}</span>
                <span class="stat-label">Fines</span>
            </div>
            <div class="stat">
                <span class="stat-value">${this.cachedResults}</span>
                <span class="stat-label">Cached</span>
            </div>
        `;
    }
}

// Initialize scanner when page loads
document.addEventListener('DOMContentLoaded', () => {
    window.scanner = new RealtimeScanner({
        scanInterval: window.SCAN_INTERVAL || 500
    });
});
