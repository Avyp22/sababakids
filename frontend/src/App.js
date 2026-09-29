import "@/App.css";
import { Toaster } from "@/components/ui/sonner";
import Explore from "@/pages/Explore";
import { useI18n } from "@/lib/i18n";

function App() {
  const { rtl } = useI18n();
  return (
    <div className="App">
      <Explore />
      <Toaster position="top-center" richColors dir={rtl ? "rtl" : "ltr"} />
    </div>
  );
}

export default App;
