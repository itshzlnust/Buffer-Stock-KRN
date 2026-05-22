// Main JavaScript for Sistem Buffer Stock SAW

document.addEventListener('DOMContentLoaded', function() {
    // Auto-hide alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            alert.style.transition = 'opacity 0.5s';
            setTimeout(() => alert.remove(), 500);
        }, 5000);
    });

    // Confirm delete actions
    const deleteForms = document.querySelectorAll('form[onsubmit]');
    deleteForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const confirmed = confirm('Yakin ingin melanjutkan?');
            if (!confirmed) {
                e.preventDefault();
            }
        });
    });
});

// Toggle section visibility
function toggleSection(id) {
    const el = document.getElementById(id);
    if (el) {
        el.classList.toggle('hidden');
        const icon = el.previousElementSibling.querySelector('i');
        if (icon) {
            icon.classList.toggle('fa-chevron-down');
            icon.classList.toggle('fa-chevron-up');
        }
    }
}

// Format number with thousand separator
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// Calculate SAW on the fly (for future enhancement)
function calculateSAW() {
    console.log('SAW Calculation triggered');
}
