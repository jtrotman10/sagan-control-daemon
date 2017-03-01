/**
 * Created by tahsmith on 1/3/17.
 */

window.onload = function () {
    var context = JSON.parse($('#data').text());
    var networks = context.networks.split(',');
    var paired = !!context.paired;
    var error = context.error;
    networks.forEach(function (network) {
        var networkElem = $(document.createElement('li'));
        networkElem.data('network', network);
        networkElem.click(selectNetwork);
        networkElem.text(network);
        networkElem.addClass('list-group-item');
        $('#networks').append(networkElem);
    });

    if (error) {
        $('#message').text(error);
    }

    if (paired) {
        $('#code-input-group').hide();
        $('#name-input-group').hide();
    }
};

function selectNetwork() {
    var network = $(this).data('network');
    $('#ssid-input').val(network);
    $('#networksModal').modal('hide');

}