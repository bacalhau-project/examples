def filter(event)
  begin
    request = event.get('request')

    if request.is_a?(String)
      # Decode URL-encoded strings
      decoded_request = CGI.unescape(request)

      # Check for invalid byte sequences and replace them if any
      if !decoded_request.valid_encoding?
        decoded_request = decoded_request.encode("UTF-8", "binary", invalid: :replace, undef: :replace, replace: "")
      end

      # Now that it's cleaned, force the encoding to UTF-8
      decoded_request.force_encoding('UTF-8')

      # Remove query parameters
      normalized_request = decoded_request.gsub(/\?.*/, '')

      # Normalize paths containing numerical IDs to a common path
      normalized_request.gsub!(/\/(\d+|idx\d+)/, '/:id')

      # Replace vertical bar and comma
      normalized_request.gsub!(/[|,]/, ':')

      # Replace long segments with placeholder
      normalized_request.gsub!(/(:\w{10,})+/) { |m| ':long_segment' }

      # Remove square brackets
      normalized_request.gsub!(/\[|\]/, '')

      # Keep only the first 3 parts of the path
      normalized_request = normalized_request.split('/').first(4).join('/')

      # Update the original event
      event.set('normalized_request', normalized_request)
    end
  rescue => e
    logger.error("Error in normalizing request #{event.get('request')}: #{e.message}")
    event.set('normalized_request', 'error')
  end

  return [event]
end
