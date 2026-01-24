// Form validation and submission handling for Check Review Console Landing Page

document.addEventListener('DOMContentLoaded', function() {
  const form = document.getElementById('demo-form');
  const successMessage = document.getElementById('form-success');
  const errorMessage = document.getElementById('form-error');

  if (!form) return;

  form.addEventListener('submit', async function(e) {
    e.preventDefault();

    // Reset messages
    successMessage.classList.add('hidden');
    errorMessage.classList.add('hidden');

    // Validate required fields
    const requiredFields = form.querySelectorAll('[required]');
    let isValid = true;

    requiredFields.forEach(field => {
      if (!field.value.trim()) {
        isValid = false;
        field.classList.add('border-red-500');
      } else {
        field.classList.remove('border-red-500');
      }
    });

    // Validate email format
    const emailField = document.getElementById('email');
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (emailField && !emailRegex.test(emailField.value)) {
      isValid = false;
      emailField.classList.add('border-red-500');
    }

    if (!isValid) {
      return;
    }

    // Add loading state
    form.classList.add('form-loading');
    const submitButton = form.querySelector('button[type="submit"]');
    const originalButtonText = submitButton.textContent;
    submitButton.textContent = 'Submitting...';

    try {
      const formData = new FormData(form);
      const response = await fetch(form.action, {
        method: 'POST',
        body: formData,
        headers: {
          'Accept': 'application/json'
        }
      });

      if (response.ok) {
        // Show success message
        successMessage.classList.remove('hidden');
        form.reset();

        // Scroll to success message
        successMessage.scrollIntoView({ behavior: 'smooth', block: 'center' });
      } else {
        throw new Error('Form submission failed');
      }
    } catch (error) {
      console.error('Form submission error:', error);
      errorMessage.classList.remove('hidden');
    } finally {
      // Remove loading state
      form.classList.remove('form-loading');
      submitButton.textContent = originalButtonText;
    }
  });

  // Remove error styling on input
  form.querySelectorAll('input, select, textarea').forEach(field => {
    field.addEventListener('input', function() {
      this.classList.remove('border-red-500');
    });
  });

  // Add navbar shadow on scroll
  const navbar = document.getElementById('navbar');
  if (navbar) {
    window.addEventListener('scroll', function() {
      if (window.scrollY > 10) {
        navbar.classList.add('navbar-scrolled');
      } else {
        navbar.classList.remove('navbar-scrolled');
      }
    });
  }
});
