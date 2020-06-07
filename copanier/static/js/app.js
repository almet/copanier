/* Handle nice phone number formatting */
function prettifyPhoneNumber(selector) {
    input = document.getElementById(selector)
    var phone = input.value;

    phone = phone.replace(/[^0-9]/g, '') // Only keep digits.
    phone = (function addSpaces(phone) {
        if (phone.length <= 2) {
            return phone
        }
        return phone.substring(0, 2) + ' ' + addSpaces(phone.substring(2))
    }(phone))

    input.value = phone;
}
