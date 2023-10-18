def register(params)
  @min_count = params["min_count"]
  @limit = params["limit"]
end

def filter(event)
  new_events = []

  aggregated_data = event.get('aggregated_data')

  if aggregated_data
    # Filter out any counter less than @min_count and only keep top @limit of each attribute
    top_data = aggregated_data.transform_values do |counts|
      filtered_counts = counts.select { |_, count| count >= @min_count }
      filtered_counts.sort_by { |_, count| -count }.first(@limit).to_h
    end

    # Publish individual event for each attribute containing the attribute type, the attribute value, and the count
    top_data.each do |key, values|
      if key == 'geoip'
        values.each do |value, count|
          # Deserialize the JSON string back into a hash
          geoip_object = JSON.parse(value)
          new_events << LogStash::Event.new(
            geoip_object.merge(
              'count' => count,
              '@timestamp' => event.get('@timestamp'),
              'tags' => ['_aggregated_geoip']
            )
          )
        end
      else
        values.each do |value, count|
          new_events << LogStash::Event.new(
            'attribute_type' => key,
            'attribute_value' => value,
            'count' => count,
            '@timestamp' => event.get('@timestamp'),
            'tags' => ['_aggregated_stats']
          )
        end
      end
    end
  end
  return new_events
end
