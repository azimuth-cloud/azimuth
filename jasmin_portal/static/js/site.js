// Make sure the has-error class gets applied to the parent form-group of any invalid controls
$('.form-control:invalid').closest('.form-group').each(function() { $(this).addClass('has-error'); });
$('.form-control').on('input', function() {
	action = this.checkValidity() ? 'removeClass' : 'addClass';
	$(this).closest('.form-group').each(function() { $(this)[action]('has-error'); });
});

// Find forms requesting the disable-on-submit functionality and enable it
//$(document).on('submit', 'form.disable-on-submit', function(){
//	$form = $(this);
//	$(document).on('submit', 'form', function(e) { e.preventDefault(); });
//	$(document).find('button[type="submit"], input, select, textarea').attr('disabled', 'disabled');
//	return true;
//});