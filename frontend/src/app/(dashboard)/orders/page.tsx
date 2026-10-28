"use client";

import React, { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorMessage } from "@/lib/api";
import {
  Button,
  Card,
  CardContent,
  DataTable,
  PageHeader,
  StatusBadge,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui";

interface OrderLine { id: number; product_name?: string | null; sku?: string | null; billing_type: string; quantity: number; unit_price: string; discount_percentage: string; total_price: string }
interface Order {
  id: number;
  order_number: string;
  quote_number?: string | null;
  customer_name?: string | null;
  status: "PENDING" | "CONFIRMED" | "FULFILLED" | "CANCELLED";
  currency: string;
  subtotal: string;
  discount_amount: string;
  tax_amount: string;
  total_amount: string;
  created_at: string;
  lines: OrderLine[];
}

const money = (v: string, cur: string) => `${cur} ${Number(v).toLocaleString("en-US", { minimumFractionDigits: 2 })}`;
const NEXT: Record<string, { label: string; to: string; danger?: boolean }[]> = {
  PENDING: [{ label: "Confirm", to: "CONFIRMED" }, { label: "Cancel", to: "CANCELLED", danger: true }],
  CONFIRMED: [{ label: "Mark fulfilled", to: "FULFILLED" }, { label: "Cancel", to: "CANCELLED", danger: true }],
  FULFILLED: [],
  CANCELLED: [],
};

export default function OrdersPage() {
  const queryClient = useQueryClient();
  const [openId, setOpenId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: orders = [], isLoading } = useQuery<Order[]>({
    queryKey: ["orders"],
    queryFn: () => api.get<Order[]>("/orders/"),
  });
  const move = useMutation({
    mutationFn: ({ id, to }: { id: number; to: string }) => api.post(`/orders/${id}/status`, { status: to }),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["orders"] });
    },
    onError: (e) => setError(errorMessage(e)),
  });

  return (
    <div className="space-y-6">
      <PageHeader title="Orders" description="Accepted quotes booked as orders. Create an order from an accepted quote on the Quotes page." />
      {error && <p className="text-sm text-rose-600">{error}</p>}
      <DataTable>
        <TableHead>
          <TableRow>
            <TableHeader>Order #</TableHeader>
            <TableHeader>Quote</TableHeader>
            <TableHeader>Customer</TableHeader>
            <TableHeader>Status</TableHeader>
            <TableHeader className="text-right">Total</TableHeader>
            <TableHeader>Booked</TableHeader>
            <TableHeader className="text-right">Actions</TableHeader>
          </TableRow>
        </TableHead>
        <tbody>
          {isLoading ? (
            <TableRow><TableCell colSpan={7} className="text-center py-8 text-slate-500">Loading…</TableCell></TableRow>
          ) : orders.length === 0 ? (
            <TableRow><TableCell colSpan={7} className="text-center py-8 text-slate-500">No orders yet.</TableCell></TableRow>
          ) : (
            orders.flatMap((o) => [
              <TableRow key={o.id} className="cursor-pointer" onClick={() => setOpenId(openId === o.id ? null : o.id)}>
                <TableCell className="font-semibold text-ink">{o.order_number}</TableCell>
                <TableCell>{o.quote_number}</TableCell>
                <TableCell>{o.customer_name}</TableCell>
                <TableCell><StatusBadge status={o.status === "FULFILLED" ? "ACTIVE" : o.status} /></TableCell>
                <TableCell className="text-right font-semibold">{money(o.total_amount, o.currency)}</TableCell>
                <TableCell className="text-slate-500">{new Date(o.created_at).toLocaleDateString()}</TableCell>
                <TableCell className="text-right space-x-2" onClick={(e) => e.stopPropagation()}>
                  {NEXT[o.status].map((n) => (
                    <Button key={n.to} size="sm" variant={n.danger ? "danger" : "primary"} onClick={() => move.mutate({ id: o.id, to: n.to })}>
                      {n.label}
                    </Button>
                  ))}
                </TableCell>
              </TableRow>,
              openId === o.id ? (
                <TableRow key={`${o.id}-lines`}>
                  <TableCell colSpan={7} className="bg-canvas-soft">
                    <Card>
                      <CardContent className="p-4 text-sm space-y-1">
                        {o.lines.map((l) => (
                          <div key={l.id} className="flex justify-between">
                            <span>{l.product_name} <span className="font-mono text-[11px] text-slate-500">{l.sku}</span> × {l.quantity} ({l.billing_type})</span>
                            <span>{money(l.total_price, o.currency)}</span>
                          </div>
                        ))}
                        {Number(o.tax_amount) > 0 && <div className="flex justify-between text-slate-600"><span>Tax</span><span>{money(o.tax_amount, o.currency)}</span></div>}
                      </CardContent>
                    </Card>
                  </TableCell>
                </TableRow>
              ) : null,
            ])
          )}
        </tbody>
      </DataTable>
    </div>
  );
}
