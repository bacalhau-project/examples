import {
  ColumnDef,
  ColumnFiltersState,
  getCoreRowModel,
  getFacetedRowModel,
  getFacetedUniqueValues,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
} from '@tanstack/react-table';
import { useState } from 'react';
import { Message } from '../page';
import Filters from './Filters';
import VMCard from './VMCard';

interface VMTableProps {
  columns: ColumnDef<Message, unknown>[];
  data: Message[];
}

export default function VMTable({ columns, data }: Readonly<VMTableProps>) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);

  const table = useReactTable({
    data,
    columns,
    state: {
      sorting,
      columnFilters,
    },
    enableGlobalFilter: true,
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,

    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFacetedRowModel: getFacetedRowModel(),
    getFacetedUniqueValues: getFacetedUniqueValues(),
  });

  return (
    <div className="flex flex-col gap-4">
      <Filters table={table} />

      <div className="grid grid-cols-3 gap-3 sm:grid-cols-5 md:grid-cols-8 lg:grid-cols-12">
        {table.getRowModel().rows.map((row) => {
          const message = row.original as Message;

          return <VMCard key={message.vm_name} message={message} />;
        })}
      </div>
    </div>
  );
}
