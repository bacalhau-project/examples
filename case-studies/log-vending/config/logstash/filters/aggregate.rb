require 'thread'

def register(params)
	def reset_aggregated_data
    @aggregated_data = {
      'status' => {},
      'ip' => {},
      'geoip' => {},
      'user_agent' => {},
      'request' => {},
      'total' => {},
    }
  end
      
  # General function to aggregate data
  def aggregate_data(key, value, count=1)
    begin
      if value
        # Convert the geoip hash to a JSON string for aggregation
        value = key == 'geoip' ? value.to_json : value
      
        @aggregated_data[key][value] ||= 0
        @aggregated_data[key][value] += count.to_i
      end
    rescue => e
      logger.error("Error in aggregating Key: #{key}, Value: #{value}, Count: #{count} : #{e.message}")
    end
  end

  reset_aggregated_data()
  $mutex = Mutex.new
  @last_flushed = 0
  @duration = params["duration"]
end

def filter(event)
  $mutex.synchronize do
    new_events = []

    # Aggregate by various attributes
    aggregate_data('status', event.get('status'))
    aggregate_data('ip', event.get('remote_addr'))
    aggregate_data('geoip', event.get('geoip'))
    aggregate_data('request', event.get('normalized_request'))
    aggregate_data('user_agent', event.get('user_agent')['name']) if event.get('user_agent')&.dig('name')

    # Aggregate totals
    aggregate_data('total', 'requests')
    aggregate_data('total', 'bytes', event.get('body_bytes_sent'))

    # If this is the first event, set the last_flushed timestamp
    if @last_flushed == 0
      @last_flushed = event.get('@timestamp')
    end

    # Flush every @duration seconds
    if event.get('@timestamp') - @last_flushed > @duration
      new_events << LogStash::Event.new(
        'aggregated_data' => @aggregated_data,
        '@timestamp' => event.get('@timestamp'),
        'tags' => ['_aggregated']
      )

      # Reset the counters
      reset_aggregated_data()

      # Update the last flushed timestamp
      @last_flushed = event.get('@timestamp')
    end
    return new_events
  end

end