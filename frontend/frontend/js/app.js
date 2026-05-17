/**
 * CatalogAI Pro - Frontend Application
 * Complete JavaScript implementation
 */

// ═══════════════════════════════════════════════════════════════════════════
// STATE MANAGEMENT
// ═══════════════════════════════════════════════════════════════════════════

let currentJobId = null;
let pollInterval = null;
let isProcessing = false;

// ═══════════════════════════════════════════════════════════════════════════
// UI INITIALIZATION
// ═══════════════════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', function() {
    initializeUI();
    checkBackendStatus();
});

function initializeUI() {
    // Drag and drop support
    const uploadArea = document.getElementById('uploadArea');
    
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });
    
    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });
    
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            document.getElementById('fileInput').files = files;
        }
    });
    
    // File input change
    document.getElementById('fileInput').addEventListener('change', function() {
        if (this.files.length > 0) {
            const fileName = this.files[0].name;
            const fileSize = (this.files[0].size / 1024 / 1024).toFixed(2);
            updateUploadLabel(`Ready: ${fileName} (${fileSize}MB)`);
        }
    });
    
    console.log('✅ UI Initialized');
}

function updateUploadLabel(text) {
    const label = document.querySelector('.upload-label');
    if (label) {
        label.textContent = text;
    }
}

function updateStatus(text, status = 'info') {
    const statusText = document.getElementById('statusText');
    const statusDot = document.getElementById('statusIndicator');
    
    if (statusText) statusText.textContent = text;
    if (statusDot) {
        statusDot.className = `status-dot status-${status}`;
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// BACKEND COMMUNICATION
// ═══════════════════════════════════════════════════════════════════════════

async function checkBackendStatus() {
    try {
        const response = await fetch(`${CONFIG.BACKEND_URL}/health`, {
            timeout: CONFIG.API_TIMEOUT
        });
        
        if (response.ok) {
            updateStatus('Connected to backend', 'success');
            console.log('✅ Backend online');
        } else {
            updateStatus('Backend error', 'error');
        }
    } catch (error) {
        updateStatus('Backend unavailable', 'error');
        console.error('Backend error:', error);
    }
}

async function createJob() {
    try {
        updateStatus('Creating job...', 'loading');
        
        const response = await fetch(`${CONFIG.BACKEND_URL}/api/jobs`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        if (!response.ok) throw new Error('Failed to create job');
        
        const data = await response.json();
        return data.job_id;
    } catch (error) {
        updateStatus('Error creating job', 'error');
        console.error('Create job error:', error);
        throw error;
    }
}

async function uploadFileToJob(jobId, file) {
    try {
        updateStatus(`Uploading ${file.name}...`, 'loading');
        
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch(
            `${CONFIG.BACKEND_URL}/api/jobs/${jobId}/upload`,
            {
                method: 'POST',
                body: formData
            }
        );
        
        if (!response.ok) throw new Error('Upload failed');
        
        const data = await response.json();
        updateStatus('File uploaded', 'success');
        return data;
    } catch (error) {
        updateStatus('Upload error', 'error');
        console.error('Upload error:', error);
        throw error;
    }
}

async function startJobProcessing(jobId) {
    try {
        updateStatus('Starting processing...', 'loading');
        
        const response = await fetch(
            `${CONFIG.BACKEND_URL}/api/jobs/${jobId}/process`,
            {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            }
        );
        
        if (!response.ok) throw new Error('Processing start failed');
        
        updateStatus('Processing started', 'success');
        return await response.json();
    } catch (error) {
        updateStatus('Processing error', 'error');
        console.error('Processing error:', error);
        throw error;
    }
}

async function getJobProgress(jobId) {
    try {
        const response = await fetch(
            `${CONFIG.BACKEND_URL}/api/jobs/${jobId}/progress`
        );
        
        if (!response.ok) throw new Error('Progress fetch failed');
        
        return await response.json();
    } catch (error) {
        console.error('Progress error:', error);
        throw error;
    }
}

async function getJobProducts(jobId) {
    try {
        const response = await fetch(
            `${CONFIG.BACKEND_URL}/api/jobs/${jobId}/products`
        );
        
        if (!response.ok) throw new Error('Products fetch failed');
        
        return await response.json();
    } catch (error) {
        console.error('Products error:', error);
        throw error;
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// FILE UPLOAD WORKFLOW
// ═══════════════════════════════════════════════════════════════════════════

async function uploadFile() {
    const fileInput = document.getElementById('fileInput');
    const file = fileInput.files[0];
    
    if (!file) {
        alert('Please select a file');
        return;
    }
    
    // Validate file size
    if (file.size > CONFIG.MAX_FILE_SIZE) {
        alert(`File too large (max: ${CONFIG.MAX_FILE_SIZE / 1024 / 1024}MB)`);
        return;
    }
    
    try {
        isProcessing = true;
        document.getElementById('uploadBtn').disabled = true;
        
        // Create job
        currentJobId = await createJob();
        console.log('✅ Job created:', currentJobId);
        
        // Upload file
        await uploadFileToJob(currentJobId, file);
        console.log('✅ File uploaded');
        
        // Start processing
        await startJobProcessing(currentJobId);
        console.log('✅ Processing started');
        
        // Show progress section
        document.querySelector('.section').style.display = 'none';
        document.getElementById('progressSection').style.display = 'block';
        document.getElementById('logsSection').style.display = 'block';
        
        // Start polling
        pollProgress();
        
    } catch (error) {
        alert(`Error: ${error.message}`);
        isProcessing = false;
        document.getElementById('uploadBtn').disabled = false;
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// PROGRESS POLLING
// ═══════════════════════════════════════════════════════════════════════════

function pollProgress() {
    // Poll every 2 seconds
    pollInterval = setInterval(async () => {
        try {
            const progress = await getJobProgress(currentJobId);
            
            // Update progress bar
            const percentage = progress.products_total > 0
                ? Math.round((progress.products_done / progress.products_total) * 100)
                : 0;
            
            document.getElementById('progressBar').style.width = percentage + '%';
            document.getElementById('progressPercent').textContent = percentage + '%';
            document.getElementById('jobStatus').textContent = progress.status;
            document.getElementById('productsCount').textContent = 
                `${progress.products_done} / ${progress.products_total}`;
            document.getElementById('estimatedCost').textContent = 
                progress.estimated_cost.toFixed(2);
            
            // Check if done
            if (progress.status === 'done' || percentage === 100) {
                clearInterval(pollInterval);
                showResults();
            }
        } catch (error) {
            console.error('Poll error:', error);
        }
    }, CONFIG.POLL_INTERVAL);
}

// ═══════════════════════════════════════════════════════════════════════════
// RESULTS DISPLAY
// ═══════════════════════════════════════════════════════════════════════════

async function showResults() {
    try {
        // Fetch final data
        const jobProducts = await getJobProducts(currentJobId);
        const jobProgress = await getJobProgress(currentJobId);
        
        // Update results
        document.getElementById('finalProductCount').textContent = 
            jobProducts.products.length;
        document.getElementById('finalCost').textContent = 
            jobProgress.actual_cost.toFixed(2);
        
        // Show results section
        document.getElementById('progressSection').style.display = 'none';
        document.getElementById('resultsSection').style.display = 'block';
        
        updateStatus('Processing complete!', 'success');
        isProcessing = false;
        
    } catch (error) {
        console.error('Results error:', error);
        alert('Error loading results');
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// DOWNLOAD FUNCTIONS
// ═══════════════════════════════════════════════════════════════════════════

function downloadExcel() {
    window.location.href = 
        `${CONFIG.BACKEND_URL}/api/jobs/${currentJobId}/export/excel`;
}

function downloadCSV() {
    window.location.href = 
        `${CONFIG.BACKEND_URL}/api/jobs/${currentJobId}/export/csv`;
}

function downloadJSON() {
    window.location.href = 
        `${CONFIG.BACKEND_URL}/api/jobs/${currentJobId}/export/json`;
}

// ═══════════════════════════════════════════════════════════════════════════
// RESET WORKFLOW
// ═══════════════════════════════════════════════════════════════════════════

function startNew() {
    // Reset state
    currentJobId = null;
    isProcessing = false;
    
    if (pollInterval) {
        clearInterval(pollInterval);
    }
    
    // Reset UI
    document.getElementById('fileInput').value = '';
    updateUploadLabel('Click to select file or drag and drop');
    document.querySelector('.section').style.display = 'block';
    document.getElementById('progressSection').style.display = 'none';
    document.getElementById('resultsSection').style.display = 'none';
    document.getElementById('logsSection').style.display = 'none';
    document.getElementById('uploadBtn').disabled = false;
    
    updateStatus('Ready', 'success');
    
    // Scroll to top
    window.scrollTo(0, 0);
}

console.log('✅ App initialized');
