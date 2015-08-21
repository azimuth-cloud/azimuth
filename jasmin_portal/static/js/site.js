// Make sure the has-error class gets applied to the parent form-group of any invalid controls
$('.form-control:invalid').closest('.form-group').each(function() { $(this).addClass('has-error'); });
$('.form-control').on('input', function() {
    action = this.checkValidity() ? 'removeClass' : 'addClass';
    $(this).closest('.form-group').each(function() { $(this)[action]('has-error'); });
});

// Find forms requesting the disable-on-submit functionality and enable it
$(document).on('submit', 'form.disable-on-submit', function(e) {
    $(document).on('submit', 'form', function(e) { e.preventDefault(); });
    $(document).find('button[type="submit"], input[type="submit"]').attr('disabled', 'disabled');
    return true;
});

// Find forms tagged as power-action forms and enable the replacement of cell content with a progress bar
$(document).on('submit', 'form.power-action', function(e) {
    // Hide all the forms in the cell, and append an element
    $(this).closest('td').find('form').hide().siblings('.progress').removeClass('hidden');
    return true;
});

// Find forms tagged as provisioning forms and enable replacing of the button content
$(document).on('submit', 'form.provisioning', function(e) {
    $(this).find('.working-message').removeClass('hidden');
    return true;
});