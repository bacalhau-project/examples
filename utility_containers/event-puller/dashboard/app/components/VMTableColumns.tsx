import { ColumnDef, FilterFn } from '@tanstack/react-table';
import { Message } from '../page';

const isInArray: FilterFn<Message> = (row, columnId, filterValue) => {
  return filterValue.includes(row.getValue(columnId));
};

export const columns = (): ColumnDef<Message>[] => [
  {
    id: 'vm_name',
    header: 'VM Name',
    accessorKey: 'vm_name',
  },
  {
    id: 'container_id',
    header: 'Container ID',
    accessorKey: 'container_id',
  },
  {
    id: 'icon_name',
    header: 'Icon Name',
    accessorKey: 'icon_name',
  },
  {
    id: 'color',
    header: 'Color',
    accessorKey: 'color',
  },
  {
    id: 'timestamp',
    header: 'Timestamp',
    accessorKey: 'timestamp',
  },
  {
    id: 'region',
    header: 'Region',
    accessorKey: 'region',
    filterFn: isInArray,
  },
];
