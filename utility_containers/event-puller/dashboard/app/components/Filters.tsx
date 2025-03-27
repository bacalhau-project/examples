import { Table } from '@tanstack/react-table';
import { TableFilter } from './TableFilter';
import { Message } from '@/page';

interface FiltersProps {
  table: Table<Message>;
}

export default function Filters({ table }: Readonly<FiltersProps>) {
  return (
    <div className="flex flex-row gap-2">
      <TableFilter
        table={table}
        column={table.getColumn('region')}
        title="Region"
        options={
          table.getColumn('region')?.getFacetedUniqueValues()
            ? Array.from(
                (table.getColumn('region')?.getFacetedUniqueValues() ?? new Map()).keys(),
              ).map((value) => {
                return { label: value, value };
              })
            : []
        }
      />
    </div>
  );
}
