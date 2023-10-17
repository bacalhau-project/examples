def filter(event)
  request = event.get('request')

  if request
    # Check for invalid byte sequences and replace them if any
    if !request.valid_encoding?
      request = request.encode("UTF-8", "binary", invalid: :replace, undef: :replace, replace: "")
    end

    # Now that it's cleaned, force the encoding to UTF-8
    request.force_encoding('UTF-8')

    # Decode URL-encoded strings
    decoded_request = CGI.unescape(request)

    # Remove query parameters
    normalized_request = decoded_request.gsub(/\?.*/, '')

    # Normalize paths containing numerical IDs to a common path
    normalized_request.gsub!(/(\/\d+)+/, '/:id')

    # Replace vertical bar and comma
    normalized_request.gsub!(/[|,]/, ':')

    # Replace long segments with placeholder
    normalized_request.gsub!(/(:\w{10,})+/) { |m| ':long_segment' }

    # Remove square brackets
    normalized_request.gsub!(/\[|\]/, '')

    # Update the original event
    event.set('normalized_request', normalized_request)
  end
  return [event]
end
