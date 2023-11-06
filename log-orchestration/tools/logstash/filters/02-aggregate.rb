require 'thread'

def register(params)
	def reset_aggregated_data
    @aggregated_data = {
      'status' => {},
      'ip' => {},
      'geoip' => {},
      'user_agent' => {},
      'bad_page_404' => {},
      'bad_caller_404' => {},
      'bad_caller_403' => {},
      'bad_caller_429' => {},
      'request' => {},
      'total' => {},
    }
    @start_time = 0
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

  $mutex = Mutex.new
  @start_time = 0
  @duration = params["duration"].to_i

  reset_aggregated_data()
end

def filter(event)
  $mutex.synchronize do
    new_events = []

    # If this is the first event, set the start_time timestamp
    if @start_time == 0
      @start_time = event.get('@timestamp')
    end

    # Flush every @duration seconds
    if event.get('@timestamp') - @start_time > @duration
      new_events << LogStash::Event.new(
        'aggregated_data' => @aggregated_data,
        '@timestamp' => @start_time,
        'end_time' => event.get('@timestamp'),
        'tags' => ['_aggregated']
      )

      # Reset the counters
      reset_aggregated_data()
      @start_time = event.get('@timestamp')
    end

    # Aggregate by various attributes
    aggregate_data('status', event.get('status'))
    aggregate_data('ip', event.get('remote_addr'))
    aggregate_data('geoip', event.get('geoip'))
    aggregate_data('request', event.get('normalized_request'))
    aggregate_data('user_agent', event.get('user_agent')['name']) if event.get('user_agent')&.dig('name')

    # Aggregate totals
    aggregate_data('total', 'requests')
    aggregate_data('total', 'bytes', event.get('body_bytes_sent'))

    # Aggregate bad requests
    case event.get('status')
    when '404'
      aggregate_data('bad_page_404', event.get('normalized_request'))
      aggregate_data('bad_caller_404', event.get('remote_addr'))
    when '403'
      aggregate_data('bad_caller_403', event.get('remote_addr'))
    when '429'
      aggregate_data('bad_caller_429', event.get('remote_addr'))
    end

    return new_events
  end

end