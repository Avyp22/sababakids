import "@/App.css";
import { Toaster } from "@/components/ui/sonner";
import Explore from "@/pages/Explore";
import NotFound from "@/pages/NotFound";
import { ROUTE } from "@/lib/routes";
import { useI18n } from "@/lib/i18n";

function App() {
  const { rtl } = useI18n();
  return (
    <div className="App">
      {ROUTE.found ? <Explore /> : <NotFound />}
      <Toaster position="top-center" richColors dir={rtl ? "rtl" : "ltr"} />
    </div>
  );
}

export default App;
