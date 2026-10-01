import { useState } from "react";
import { Flag } from "lucide-react";
import { toast } from "sonner";
import { reportItem } from "@/lib/api";
import { track } from "@/lib/analytics";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const REASONS = ["wrong_category", "not_for_kids", "closed", "wrong_info", "other"];

// "Report a problem" link + small inline form (places and events).
export function ReportButton({ itemId, kind, name, className }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("wrong_category");
  const [comment, setComment] = useState("");
  const [sending, setSending] = useState(false);

  const send = async () => {
    setSending(true);
    try {
      await reportItem({ item_id: itemId, kind, name, reason, comment });
      track("report", `${kind}-${reason}`);
      toast.success(t("reportThanks"));
      setOpen(false);
      setComment("");
    } catch {
      toast.error(t("loadError"));
    } finally {
      setSending(false);
    }
  };

  if (!open) {
    return (
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); setOpen(true); }}
        className={cn("inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground underline-offset-2 hover:underline", className)}
        data-testid={`report-${itemId}`}
      >
        <Flag className="w-3 h-3" /> {t("report")}
      </button>
    );
  }

  return (
    <div className={cn("w-full rounded-xl border border-border bg-muted/40 p-3 space-y-2", className)} onClick={(e) => e.stopPropagation()}>
      <p className="text-xs font-semibold">{t("reportTitle")}</p>
      <div className="flex flex-wrap gap-1.5">
        {REASONS.map((r) => (
          <button
            key={r}
            type="button"
            onClick={() => setReason(r)}
            aria-pressed={reason === r}
            className={cn(
              "px-2 h-7 rounded-lg text-[11px] font-semibold border",
              reason === r ? "bg-primary text-primary-foreground border-primary" : "bg-background border-border"
            )}
          >
            {t(`rr_${r}`)}
          </button>
        ))}
      </div>
      <textarea
        value={comment}
        onChange={(e) => setComment(e.target.value.slice(0, 500))}
        placeholder={t("reportComment")}
        dir="auto"
        rows={2}
        className="w-full rounded-lg border border-border bg-background px-2 py-1 text-xs"
      />
      <div className="flex justify-end gap-2">
        <button type="button" onClick={() => setOpen(false)} className="px-3 h-8 rounded-lg text-xs">{t("cancel")}</button>
        <button
          type="button"
          onClick={send}
          disabled={sending}
          className="px-3 h-8 rounded-lg text-xs font-semibold bg-primary text-primary-foreground disabled:opacity-60"
        >
          {t("reportSend")}
        </button>
      </div>
    </div>
  );
}
