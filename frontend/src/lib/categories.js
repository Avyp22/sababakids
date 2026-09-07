import {
  Sparkles, TreePine, Blocks, Landmark, PawPrint, Waves,
  Baby, FerrisWheel, Fish, Ticket, PartyPopper, GraduationCap,
} from "lucide-react";

export const CATEGORIES = [
  { id: "all", label: "All", icon: Sparkles, color: "#E05A47" },
  { id: "park", label: "Parks", icon: TreePine, color: "#15803D" },
  { id: "playground", label: "Playgrounds", icon: Blocks, color: "#F5A623" },
  { id: "beach", label: "Beaches", icon: Waves, color: "#0284C7" },
  { id: "museum", label: "Museums", icon: Landmark, color: "#7C3AED" },
  { id: "zoo", label: "Zoos", icon: PawPrint, color: "#B45309" },
  { id: "aquarium", label: "Aquariums", icon: Fish, color: "#0891B2" },
  { id: "water_park", label: "Water Parks", icon: Waves, color: "#0EA5E9" },
  { id: "amusement_park", label: "Amusement", icon: FerrisWheel, color: "#DB2777" },
  { id: "indoor_play", label: "Indoor Play", icon: Baby, color: "#E05A47" },
];

export const CATEGORY_MAP = Object.fromEntries(CATEGORIES.map((c) => [c.id, c]));

export const AGE_GROUPS = [
  { id: "0-2", label: "Baby", sub: "0-2" },
  { id: "3-5", label: "Toddler", sub: "3-5" },
  { id: "6-9", label: "Kid", sub: "6-9" },
  { id: "10+", label: "Tween", sub: "10+" },
];

export const EVENT_ICONS = {
  show: Ticket,
  festival: PartyPopper,
  workshop: GraduationCap,
  activity: Sparkles,
};
