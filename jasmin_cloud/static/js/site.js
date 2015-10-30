// Make sure the has-error class gets applied to the parent form-group of any invalid controls
$('.form-control:invalid').closest('.form-group').each(function() { $(this).addClass('has-error'); });
$('.form-control').on('input', function() {
    var action = this.checkValidity() ? 'removeClass' : 'addClass';
    $(this).closest('.form-group').each(function() { $(this)[action]('has-error'); });
});

// Enable preview for markdown editors
//  In order to ensure we use the same rendering algorithm, we use an Ajax callback
//  We throttle ajax calls using a timeout
$('.markdown-editor').each(function() {
    var $input = $(this);
    var $preview = $('<div class="markdown-preview"><header>Live preview</header><div class="content"></div></div>');
    $preview.hide();
    $input.parent().append($preview);
    var timeout;
    function updatePreview() {
        if( $input.val() === "" ) {
            // If there is no content, hide the preview
            $preview.hide();
        } else {
            // Otherwise, get a preview to show
            $preview.find('.content').load(
                '/markdown_preview',
                { 'markdown' : $input.val() },
                function() { $preview.show(); }
            );
        }
    }
    $input.on('input', function() {
        // Clear any existing timeout and set a new one
        clearTimeout(timeout);
        timeout = setTimeout(updatePreview, 1000);
    });
    updatePreview();
});

// Confirmation dialog for links
$(document).on('click', 'a.confirm', function(e) {
    // Show a confirm dialog that redirects to the href of the link on confirm
    var $link = $(this);
    bootbox.confirm($link.data('confirm-message'), function(result) {
        if( result ) window.location.href = $link.attr('href');
    });
    // Prevent the default behaviour of the link click
    e.preventDefault();
    return false;
});

/**
 * In order to allow a modular framework for attaching functionality on form submission, we use
 * a custom event, submit-confirmed, that fires only once a form submission has been confirmed
 * if required 
 */

$(document).on('submit', 'form', function(e) {
    var $form = $(this);
    if( $form.hasClass('confirm') ) {
        bootbox.confirm($(this).data('confirm-message'), function(result) {
            if( result ) {
                // If the user confirmed, re-submit the form without the class
                $form.removeClass('confirm');
                $form.submit();
            }
        });
        // Prevent the submission this time
        e.preventDefault();
        return false;
    }
    // Otherwise, just fire the submit-confirmed event and allow propagation of the event
    $form.trigger('submit-confirmed');
    return true;
});

// Find forms requesting the disable-on-submit functionality and enable it
$(document).on('submit-confirmed', 'form.disable-on-submit', function(e) {
    $(document).on('submit', 'form', function(e) { e.preventDefault(); return false; });
    $(document).find('button[type="submit"], input[type="submit"]').attr('disabled', 'disabled');
    $(document).find('a.btn').addClass('disabled');
    return true;
});

// Find forms tagged as power-action forms and enable the replacement of cell content with a progress bar
$(document).on('submit-confirmed', 'form.power-action', function(e) {
    // Hide all the forms in the cell, and append an element
    $(this).closest('td').find('form, a').hide().siblings('.progress').removeClass('hidden');
    return true;
});

// Find forms tagged as provisioning forms and enable replacing of the button content
$(document).on('submit-confirmed', 'form.working', function(e) {
    $(this).find('.working-message').removeClass('hidden');
    return true;
});
