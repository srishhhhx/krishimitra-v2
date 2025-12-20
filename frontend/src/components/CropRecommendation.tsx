import React, { useState } from "react";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { CheckCircle, Sprout, Droplets, Thermometer, Calendar } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import { useTranslation } from "react-i18next";

interface CropRecommendationResult {
  name: string;
  suitability: "Excellent" | "Good" | "Average" | "Poor";
  score: number;
  growingSeason: string;
  waterRequirement: "Low" | "Medium" | "High";
  specialNotes: string;
  benefits: string[];
}

const CropRecommendation: React.FC = () => {
  const { toast } = useToast();
  const { t } = useTranslation();
  const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";
  
  // Form state
  const [nitrogen, setNitrogen] = useState<string>("");
  const [phosphorus, setPhosphorus] = useState<string>("");
  const [potassium, setPotassium] = useState<string>("");
  const [temperature, setTemperature] = useState<string>("");
  const [humidity, setHumidity] = useState<string>("");
  const [ph, setPh] = useState<string>("");
  const [rainfall, setRainfall] = useState<string>("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [recommendation, setRecommendation] = useState<CropRecommendationResult | null>(null);

  // Crop information database
  const cropDatabase: { [key: string]: Omit<CropRecommendationResult, 'name'> } = {
    "rice": {
      suitability: "Excellent",
      score: 94,
      growingSeason: "June-November (Kharif) | December-April (Rabi in irrigated areas)",
      waterRequirement: "High",
      specialNotes: "World's most important staple crop, perfectly adapted to flooded paddy systems. Requires 1000-2000mm annual rainfall or equivalent irrigation. Thrives in clayey soils with pH 5.5-6.5. Excellent carbon sequestration in flooded fields.",
      benefits: [
        "Exceptional yield potential (6-8 tons/ha with modern varieties)",
        "Global staple feeding 3.5 billion people daily",
        "Guaranteed government procurement with MSP support",
        "Multiple varieties: Basmati (premium export), IR varieties (high yield)",
        "Methane production supports biogas generation",
        "Straw utilization for paper, construction, and animal feed",
        "Cultural significance and food security cornerstone",
        "Flood-tolerant varieties available for climate resilience"
      ]
    },
    "maize": {
      suitability: "Excellent",
      score: 89,
      growingSeason: "February-June (Rabi) | June-October (Kharif) | October-February (Winter)",
      waterRequirement: "Medium",
      specialNotes: "Queen of cereals with highest genetic yield potential among food grains. Adaptable to diverse agro-climatic zones from sea level to 2700m altitude. Requires well-drained soils with pH 6.0-7.5. C4 photosynthesis makes it highly efficient.",
      benefits: [
        "Highest productivity potential (8-12 tons/ha) among cereals",
        "Triple season cultivation maximizes land utilization",
        "Industrial applications: starch, ethanol, biodegradable plastics",
        "Livestock feed industry backbone (60% of feed requirement)",
        "Poultry industry essential - supports ₹80,000 crore sector",
        "Export opportunities to Southeast Asia and Middle East",
        "Drought-tolerant hybrids reduce water stress risks",
        "Value addition: corn flakes, popcorn, sweet corn varieties"
      ]
    },
    "chickpea": {
      suitability: "Excellent",
      score: 86,
      growingSeason: "October-March (Rabi) | August-December (Late Kharif in hills)",
      waterRequirement: "Low",
      specialNotes: "King of pulses with exceptional drought tolerance and nitrogen-fixing capability. Fixes 140-200kg N/ha, equivalent to ₹8,000-12,000 fertilizer value. Thrives in black cotton soils with pH 6.0-7.5. Cold-tolerant varieties withstand frost.",
      benefits: [
        "Superior protein quality (20-22%) with essential amino acids",
        "Biological nitrogen fixation saves ₹8,000-12,000/ha in fertilizers",
        "Drought resilience - survives on 300-400mm annual rainfall",
        "Premium export commodity to Middle East and Europe",
        "Soil health improvement through deep root system (1.5m)",
        "Intercropping compatibility with wheat, mustard, coriander",
        "Processing industry: besan, roasted chana, hummus production",
        "Medicinal properties: diabetes management, heart health"
      ]
    },
    "kidneybeans": {
      suitability: "Excellent",
      score: 85,
      growingSeason: "October-March (Rabi) | June-September (Kharif in hills)",
      waterRequirement: "Medium",
      specialNotes: "Premium pulse crop with exceptional export demand, particularly to USA and European markets. Requires cool, dry weather during maturity. Thrives in well-drained loamy soils with pH 6.0-7.0. Rajma cultivation concentrated in hilly regions for quality.",
      benefits: [
        "Premium export prices: ₹8,000-15,000 per quintal internationally",
        "Exceptional protein content (22-24%) with complete amino acids",
        "Major export commodity to USA, Canada, and European Union",
        "Nitrogen fixation capability reduces fertilizer dependency",
        "High-value processing: canned beans, ready-to-eat products",
        "Medicinal properties: heart health, diabetes management",
        "Intercropping potential with maize and wheat systems",
        "Government support through export promotion schemes"
      ]
    },
    "pigeonpeas": {
      suitability: "Excellent",
      score: 84,
      growingSeason: "June-December (Kharif) | October-March (Rabi in irrigated areas)",
      waterRequirement: "Low",
      specialNotes: "Arhar/Tur dal - India's second most important pulse crop. Exceptional drought tolerance with deep taproot (2-3m). Fixes 40-200kg N/ha depending on variety. Suitable for intercropping with cotton, sugarcane, and cereals. Perennial types available.",
      benefits: [
        "Outstanding drought resilience survives on 600-650mm rainfall",
        "Deep root system (2-3m) accesses subsoil moisture and nutrients",
        "Biological nitrogen fixation worth ₹6,000-10,000/ha in fertilizers",
        "Intercropping increases system productivity by 30-60%",
        "Multiple products: dal, green pods, fodder, fuel wood",
        "Long shelf life (2-3 years) provides price stability",
        "Processing industry: split dal, flour, ready-to-cook products",
        "Climate resilience ideal for rainfed agriculture systems"
      ]
    },
    "mothbeans": {
      suitability: "Good",
      score: 79,
      growingSeason: "July-October (Kharif) | February-May (Summer in arid zones)",
      waterRequirement: "Low",
      specialNotes: "Desert bean with exceptional drought tolerance, survives on 250-400mm rainfall. Excellent soil binder preventing erosion in arid regions. Fixes 30-40kg N/ha. Suitable for marginal lands where other crops fail. Heat tolerance up to 48°C.",
      benefits: [
        "Extreme drought tolerance - survives on 250-400mm annual rainfall",
        "Heat resilience withstands temperatures up to 48°C",
        "Soil conservation through extensive root system and ground cover",
        "Marginal land utilization where other crops cannot survive",
        "Dual purpose: nutritious grain (22% protein) and quality fodder",
        "Low input costs with minimal fertilizer and pesticide requirements",
        "Climate change adaptation crop for water-scarce regions",
        "Traditional food security crop in Rajasthan and Gujarat"
      ]
    },
    "mungbean": {
      suitability: "Excellent",
      score: 88,
      growingSeason: "March-June (Summer) | July-October (Kharif) | November-February (Late Rabi)",
      waterRequirement: "Medium",
      specialNotes: "Golden gram with remarkable adaptability and short duration (60-90 days). Excellent green manure crop when incorporated at flowering. Fixes 40-60kg N/ha. Tolerates waterlogging better than other pulses. Suitable for mechanized harvesting.",
      benefits: [
        "Ultra-short duration enables 3 crops per year in irrigated areas",
        "Premium protein source (24%) with easy digestibility",
        "Sprout industry worth ₹2,000 crore annually in India",
        "Export potential to USA, Canada, and European markets",
        "Intercrop compatibility with sugarcane, cotton, and maize",
        "Green manure value when incorporated at 50% flowering",
        "Processing versatility: dal, noodles, papad, and health foods",
        "Climate resilience with heat and moisture stress tolerance"
      ]
    },
    "blackgram": {
      suitability: "Excellent",
      score: 87,
      growingSeason: "July-October (Kharif) | February-May (Summer)",
      waterRequirement: "Medium",
      specialNotes: "Premium pulse crop known as 'Urad Dal' - highly valued for its nutritional density and culinary versatility. Excellent nitrogen-fixing properties improve soil fertility for subsequent crops. Thrives in well-drained soils with pH 6.0-7.5.",
      benefits: [
        "Exceptional protein content (24-26%) with complete amino acid profile",
        "Premium market rates - 20-30% higher than other pulses",
        "Biological nitrogen fixation reduces fertilizer costs by 40-60kg N/ha",
        "Essential ingredient in South Indian cuisine (dosa, idli, vada)",
        "Drought tolerance once established - suitable for rainfed agriculture",
        "Short duration (90-120 days) allows for crop rotation flexibility",
        "High demand in domestic and export markets",
        "Medicinal properties - rich in iron, calcium, and B-vitamins"
      ]
    },
    "lentil": {
      suitability: "Excellent",
      score: 88,
      growingSeason: "October-March (Rabi) | September-January (Late sowing varieties)",
      waterRequirement: "Low",
      specialNotes: "Masoor dal - premium pulse with excellent cold tolerance and short duration (110-130 days). Requires cool, dry weather during maturity. Thrives in well-drained soils with pH 6.0-7.5. Excellent preceding crop for rice due to nitrogen fixation.",
      benefits: [
        "Premium protein source (25-28%) with essential amino acids",
        "Short duration (110-130 days) fits well in cropping systems",
        "Cold tolerance allows cultivation in northern plains and hills",
        "Export potential to Middle East, Europe, and North America",
        "Nitrogen fixation (80-100kg N/ha) benefits succeeding crops",
        "Processing versatility: whole dal, split dal, flour, papad",
        "Medicinal properties: iron-rich, heart health, weight management",
        "Low water requirement ideal for water-scarce regions"
      ]
    },
    "pomegranate": {
      suitability: "Average",
      score: 68,
      growingSeason: "Year-round (Perennial)",
      waterRequirement: "Medium",
      specialNotes: "High-value fruit crop, requires initial investment",
      benefits: ["High value crop", "Long-term returns", "Health benefits", "Export market"]
    },
    "banana": {
      suitability: "Excellent",
      score: 91,
      growingSeason: "Year-round planting (Perennial) | Peak harvest: March-May, September-November",
      waterRequirement: "High",
      specialNotes: "World's largest herbaceous flowering plant with exceptional productivity (40-80 tons/ha). Requires 1200-1500mm annual rainfall with high humidity (75-85%). Thrives in deep, well-drained alluvial soils with pH 6.0-7.5. Tissue culture ensures disease-free planting.",
      benefits: [
        "Exceptional productivity: 40-80 tons/ha (highest among fruits)",
        "Continuous income stream with 12-15 month crop cycle",
        "Zero waste crop: fruit, flower, stem, leaf all commercially valuable",
        "Export potential worth ₹5,000 crore to Middle East and Europe",
        "Processing industry: chips, powder, wine, fiber production",
        "Nutritional powerhouse: potassium, vitamin B6, dietary fiber",
        "Intercropping opportunities with coconut, areca nut, spices",
        "Climate resilience with wind-resistant varieties available"
      ]
    },
    "mango": {
      suitability: "Excellent",
      score: 92,
      growingSeason: "Year-round (Perennial) | Flowering: December-February | Harvest: March-July",
      waterRequirement: "Medium",
      specialNotes: "King of fruits with 25-30 year productive lifespan generating ₹2-5 lakh annual income per acre at maturity. Requires distinct dry and wet seasons. Thrives in well-drained soils with pH 5.5-7.5. Grafted varieties ensure quality and early bearing.",
      benefits: [
        "Premium returns: ₹2-5 lakh per acre annually at full bearing",
        "Long-term asset with 25-30 year productive lifespan",
        "Export market worth ₹4,000 crore (UAE, UK, USA, Bangladesh)",
        "Processing industry: pulp, juice, pickle, leather, ice cream",
        "Alphonso variety commands ₹1,000-2,000 per dozen premium",
        "Intercropping income during initial 5-7 years establishment",
        "Carbon sequestration and environmental benefits",
        "Cultural significance and religious importance in India"
      ]
    },
    "grapes": {
      suitability: "Average",
      score: 72,
      growingSeason: "Year-round (Perennial)",
      waterRequirement: "Medium",
      specialNotes: "High-value crop, requires technical knowledge and investment",
      benefits: ["High value", "Wine industry", "Export potential", "Premium market"]
    },
    "watermelon": {
      suitability: "Good",
      score: 77,
      growingSeason: "February-May (Summer)",
      waterRequirement: "High",
      specialNotes: "Summer crop with high water content, good for hot climates",
      benefits: ["Summer crop", "High water content", "Quick returns", "Good demand"]
    },
    "muskmelon": {
      suitability: "Good",
      score: 76,
      growingSeason: "February-May (Summer)",
      waterRequirement: "Medium",
      specialNotes: "Sweet fruit crop, suitable for semi-arid regions",
      benefits: ["Sweet fruit", "Good market", "Nutritious", "Heat tolerant"]
    },
    "apple": {
      suitability: "Poor",
      score: 45,
      growingSeason: "Year-round (Perennial)",
      waterRequirement: "Medium",
      specialNotes: "Requires cool climate, not suitable for tropical regions",
      benefits: ["Premium fruit", "High value", "Health benefits", "Storage life"]
    },
    "orange": {
      suitability: "Average",
      score: 65,
      growingSeason: "Year-round (Perennial)",
      waterRequirement: "Medium",
      specialNotes: "Citrus crop, requires specific soil and climate conditions",
      benefits: ["Vitamin C rich", "Good market", "Processing industry", "Long shelf life"]
    },
    "papaya": {
      suitability: "Excellent",
      score: 93,
      growingSeason: "Year-round planting | Harvest starts 8-12 months | Peak: October-March",
      waterRequirement: "Medium",
      specialNotes: "Fastest ROI among fruit crops with harvest beginning in 8-12 months. Requires frost-free climate with 25-30°C temperature. Thrives in well-drained sandy loam with pH 6.0-7.0. Papain enzyme extraction adds value to raw fruits.",
      benefits: [
        "Fastest returns: harvest begins in 8-12 months from planting",
        "High productivity: 80-150 fruits per plant annually",
        "Papain enzyme industry worth ₹500 crore (pharmaceutical use)",
        "Export opportunities to Middle East and European markets",
        "Nutritional powerhouse: Vitamin C, A, folate, potassium",
        "Medicinal applications: digestive health, anti-inflammatory",
        "Processing potential: juice, candy, pickle, cosmetics",
        "Space-efficient cultivation suitable for small farmers"
      ]
    },
    "coconut": {
      suitability: "Excellent",
      score: 90,
      growingSeason: "Year-round (Perennial) | Peak harvest: December-May",
      waterRequirement: "Medium",
      specialNotes: "Kalpavriksha (tree of life) with 75-80 year productive lifespan. Requires coastal climate with high humidity (70-80%). Thrives in sandy loam soils with pH 5.2-8.0. Intercropping potential maximizes land utilization and income.",
      benefits: [
        "Complete utilization: water, oil, fiber, shell, wood - zero waste",
        "Long productive life (75-80 years) ensures generational income",
        "Coconut oil industry worth ₹25,000 crore annually in India",
        "Export potential: oil, desiccated coconut, coir products",
        "Intercropping opportunities with spices, vegetables, fodder crops",
        "Value addition: virgin oil, milk, flour, sugar, vinegar",
        "Sustainable farming with carbon sequestration benefits",
        "Cultural and religious significance across coastal regions"
      ]
    },
    "cotton": {
      suitability: "Good",
      score: 82,
      growingSeason: "April-November (Kharif) | October-March (Irrigated Rabi in South)",
      waterRequirement: "High",
      specialNotes: "White gold of India supporting ₹5 lakh crore textile industry. Bt cotton technology provides built-in pest resistance. Requires 500-800mm rainfall with supplemental irrigation. Deep black cotton soils ideal with pH 5.8-8.0.",
      benefits: [
        "Premium cash crop with ₹1.5-2.5 lakh/ha gross returns",
        "Textile industry backbone employing 45 million people",
        "Export earnings of $13 billion annually for India",
        "Bt technology reduces pesticide use by 30-50%",
        "Cottonseed oil production (secondary income source)",
        "Organic cotton premium markets in Europe and USA",
        "Mechanization potential for planting and harvesting",
        "Government support through MSP and technology missions"
      ]
    },
    "jute": {
      suitability: "Excellent",
      score: 86,
      growingSeason: "April-August (Kharif) | Peak sowing: May-June",
      waterRequirement: "High",
      specialNotes: "Golden fiber with exceptional eco-friendly properties. Requires 1200-1500mm rainfall with high humidity (80-90%). Thrives in alluvial soils of Ganges delta. Complete biodegradability makes it environmentally superior to synthetic fibers.",
      benefits: [
        "Eco-friendly alternative to plastic bags and synthetic fibers",
        "Export earnings of ₹2,000 crore annually from fiber and products",
        "Complete biodegradability supports environmental sustainability",
        "Industrial applications: textiles, carpets, ropes, geotextiles",
        "Government support through Jute Technology Mission",
        "Employment generation for 4 million people in value chain",
        "Carbon sequestration and oxygen production benefits",
        "Diversification potential: jute sticks for paper and particle boards"
      ]
    },
    "coffee": {
      suitability: "Good",
      score: 81,
      growingSeason: "Year-round (Perennial) | Harvest: November-February",
      waterRequirement: "High",
      specialNotes: "Premium beverage crop requiring specific altitude (600-1600m) and climate. Shade-grown coffee supports biodiversity conservation. Requires well-drained soils with pH 6.0-6.5. Arabica commands premium prices over Robusta varieties.",
      benefits: [
        "Premium export commodity earning ₹5,500 crore annually",
        "Shade cultivation supports biodiversity and forest conservation",
        "Arabica variety commands 30-50% premium over Robusta",
        "Specialty coffee market growing at 20% annually globally",
        "Intercropping with spices (cardamom, pepper) increases income",
        "Processing value addition: roasted, ground, instant coffee",
        "Sustainable farming practices enhance soil health",
        "Tourism potential through coffee plantation visits and experiences"
      ]
    }
  };

  const generateRecommendation = async () => {
    if (!nitrogen || !phosphorus || !potassium || !temperature || !humidity || !ph || !rainfall) {
      toast({ 
        title: t('crop_recommendation.missing_info'), 
        description: t('crop_recommendation.missing_info_desc'), 
        variant: "destructive" 
      });
      return;
    }

    const payload = {
      N: parseFloat(nitrogen),
      P: parseFloat(phosphorus),
      K: parseFloat(potassium),
      temperature: parseFloat(temperature),
      humidity: parseFloat(humidity),
      ph: parseFloat(ph),
      rainfall: parseFloat(rainfall),
    };

    setIsGenerating(true);
    try {
      const token = localStorage.getItem("access_token");
      const res = await fetch(`${API_BASE}/crop_predict/predict`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(payload),
      });
      
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data?.detail || "Prediction failed");
      }

      // Get crop info from database or use default
      const cropName = data.predicted_crop?.toLowerCase() || "unknown";
      const cropInfo = cropDatabase[cropName] || {
        suitability: "Average" as const,
        score: 60,
        growingSeason: t('crop_recommendation.fallback.growing_season'),
        waterRequirement: "Medium" as const,
        specialNotes: t('crop_recommendation.fallback.special_notes'),
        benefits: t('crop_recommendation.fallback.benefits', { returnObjects: true })
      };

      setRecommendation({
        name: data.predicted_crop || "Unknown Crop",
        ...cropInfo
      });

      toast({ 
        title: t('crop_recommendation.recommendation_ready'), 
        description: t('crop_recommendation.recommendation_ready_desc') 
      });
    } catch (e: any) {
      toast({ 
        title: t('crop_recommendation.error'), 
        description: e?.message || t('crop_recommendation.failed_recommendation'), 
        variant: "destructive" 
      });
    }
    setIsGenerating(false);
  };

  const resetForm = () => {
    setNitrogen("");
    setPhosphorus("");
    setPotassium("");
    setTemperature("");
    setHumidity("");
    setPh("");
    setRainfall("");
    setRecommendation(null);
  };

  const getSuitabilityColor = (suitability: string) => {
    switch (suitability) {
      case "Excellent":
        return "bg-green-100 text-green-800";
      case "Good":
        return "bg-blue-100 text-blue-800";
      case "Average":
        return "bg-amber-100 text-amber-800";
      case "Poor":
        return "bg-red-100 text-red-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <Card className="lg:col-span-1">
        <CardHeader>
          <CardTitle>{t('crop_recommendation.title')}</CardTitle>
          <CardDescription>
            {t('crop_recommendation.description')}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="nitrogen">{t('crop_recommendation.nitrogen')}</Label>
                <Input 
                  id="nitrogen" 
                  type="number" 
                  step="0.1" 
                  value={nitrogen} 
                  onChange={(e) => setNitrogen(e.target.value)} 
                  placeholder="e.g., 90" 
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="phosphorus">{t('crop_recommendation.phosphorus')}</Label>
                <Input 
                  id="phosphorus" 
                  type="number" 
                  step="0.1" 
                  value={phosphorus} 
                  onChange={(e) => setPhosphorus(e.target.value)} 
                  placeholder="e.g., 42" 
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="potassium">{t('crop_recommendation.potassium')}</Label>
                <Input 
                  id="potassium" 
                  type="number" 
                  step="0.1" 
                  value={potassium} 
                  onChange={(e) => setPotassium(e.target.value)} 
                  placeholder="e.g., 37" 
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="temperature">{t('crop_recommendation.temperature')}</Label>
                <Input 
                  id="temperature" 
                  type="number" 
                  step="0.1" 
                  value={temperature} 
                  onChange={(e) => setTemperature(e.target.value)} 
                  placeholder="e.g., 28" 
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="humidity">{t('crop_recommendation.humidity')}</Label>
                <Input 
                  id="humidity" 
                  type="number" 
                  step="0.1" 
                  value={humidity} 
                  onChange={(e) => setHumidity(e.target.value)} 
                  placeholder="e.g., 65" 
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="ph">{t('crop_recommendation.soil_ph')}</Label>
                <Input 
                  id="ph" 
                  type="number" 
                  step="0.1" 
                  value={ph} 
                  onChange={(e) => setPh(e.target.value)} 
                  placeholder="e.g., 6.5" 
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="rainfall">{t('crop_recommendation.rainfall')}</Label>
                <Input 
                  id="rainfall" 
                  type="number" 
                  step="0.1" 
                  value={rainfall} 
                  onChange={(e) => setRainfall(e.target.value)} 
                  placeholder="e.g., 200" 
                />
              </div>
            </div>
          </form>
        </CardContent>
        <CardFooter className="flex justify-between">
          <Button variant="outline" onClick={resetForm} disabled={isGenerating}>
            {t('crop_recommendation.reset')}
          </Button>
          <Button onClick={generateRecommendation} disabled={isGenerating}>
            {isGenerating ? t('crop_recommendation.analyzing') : t('crop_recommendation.get_recommendation')}
          </Button>
        </CardFooter>
      </Card>

      <Card className="lg:col-span-2">
        {recommendation ? (
          <>
            <CardHeader>
              <CardTitle>{t('crop_recommendation.crop_recommendation')}</CardTitle>
              <CardDescription>
                {t('crop_recommendation.based_on_conditions')}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="recommendation">
                <TabsList className="grid w-full grid-cols-2">
                  <TabsTrigger value="recommendation">{t('crop_recommendation.recommendation_tab')}</TabsTrigger>
                  <TabsTrigger value="details">{t('crop_recommendation.details_tab')}</TabsTrigger>
                </TabsList>
                
                <TabsContent value="recommendation" className="pt-4">
                  <div className="space-y-6">
                    <div className="mb-6">
                      <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 mb-4">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-sm text-slate-600 font-medium mb-1">{t('crop_recommendation.recommended_crop')}</p>
                            <h2 className="text-xl font-semibold text-slate-800 capitalize">
                              {recommendation.name}
                            </h2>
                          </div>
                          <Badge className={getSuitabilityColor(recommendation.suitability)}>
                            {t(`crop_recommendation.suitability_levels.${recommendation.suitability.toLowerCase()}`)} ({recommendation.score}%)
                          </Badge>
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200 p-4 rounded-xl text-center shadow-sm hover:shadow-md transition-shadow">
                        <div className="w-10 h-10 bg-blue-500 rounded-full flex items-center justify-center mx-auto mb-3">
                          <Calendar className="h-5 w-5 text-white" />
                        </div>
                        <p className="text-sm font-semibold text-blue-900 mb-1">{t('crop_recommendation.growing_seasons')}</p>
                        <p className="text-xs text-blue-700 leading-relaxed">{recommendation.growingSeason}</p>
                      </div>
                      <div className="bg-gradient-to-br from-cyan-50 to-teal-50 border border-cyan-200 p-4 rounded-xl text-center shadow-sm hover:shadow-md transition-shadow">
                        <div className="w-10 h-10 bg-cyan-500 rounded-full flex items-center justify-center mx-auto mb-3">
                          <Droplets className="h-5 w-5 text-white" />
                        </div>
                        <p className="text-sm font-semibold text-cyan-900 mb-1">{t('crop_recommendation.water_needs')}</p>
                        <p className="text-xs text-cyan-700">{t(`crop_recommendation.water_requirements.${recommendation.waterRequirement.toLowerCase()}`)}</p>
                      </div>
                      <div className="bg-gradient-to-br from-green-50 to-emerald-50 border border-green-200 p-4 rounded-xl text-center shadow-sm hover:shadow-md transition-shadow">
                        <div className="w-10 h-10 bg-green-500 rounded-full flex items-center justify-center mx-auto mb-3">
                          <Sprout className="h-5 w-5 text-white" />
                        </div>
                        <p className="text-sm font-semibold text-green-900 mb-1">{t('crop_recommendation.suitability')}</p>
                        <p className="text-xs text-green-700 font-bold">{recommendation.score}% {t('crop_recommendation.match')}</p>
                      </div>
                    </div>

                    <div className="bg-gradient-to-br from-amber-50 to-orange-50 border border-amber-200 p-4 rounded-xl shadow-sm">
                      <div className="flex items-start space-x-2 mb-2">
                        <div className="w-2 h-2 bg-amber-500 rounded-full mt-2 flex-shrink-0"></div>
                        <h4 className="text-sm font-semibold text-amber-900 tracking-wide">{t('crop_recommendation.agricultural_insights')}</h4>
                      </div>
                      <p className="text-sm text-amber-800 leading-relaxed">{recommendation.specialNotes}</p>
                    </div>

                    <div className="bg-gradient-to-br from-green-50 to-emerald-50 border border-green-200 p-4 rounded-xl shadow-sm">
                      <div className="flex items-center space-x-2 mb-3">
                        <div className="w-6 h-6 bg-green-500 rounded-full flex items-center justify-center">
                          <CheckCircle className="w-4 h-4 text-white" />
                        </div>
                        <h4 className="text-sm font-semibold text-green-900 tracking-wide">{t('crop_recommendation.strategic_advantages')}</h4>
                      </div>
                      <div className="grid gap-3">
                        {recommendation.benefits.map((benefit, idx) => (
                          <div key={idx} className="flex items-start space-x-3 bg-white/60 p-3 rounded-lg border border-green-100">
                            <div className="w-1.5 h-1.5 bg-green-500 rounded-full mt-2 flex-shrink-0"></div>
                            <span className="text-sm text-green-800 font-medium leading-relaxed">{benefit}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </TabsContent>
                
                <TabsContent value="details" className="pt-4">
                  <div className="space-y-4">
                    <div className="bg-slate-50 p-4 rounded-lg">
                      <h4 className="font-medium text-slate-800 mb-2">{t('crop_recommendation.soil_conditions_analysis')}</h4>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                        <div>
                          <p className="text-slate-600">Nitrogen</p>
                          <p className="font-medium">{nitrogen} kg/ha</p>
                        </div>
                        <div>
                          <p className="text-slate-600">Phosphorus</p>
                          <p className="font-medium">{phosphorus} kg/ha</p>
                        </div>
                        <div>
                          <p className="text-slate-600">Potassium</p>
                          <p className="font-medium">{potassium} kg/ha</p>
                        </div>
                        <div>
                          <p className="text-slate-600">pH Level</p>
                          <p className="font-medium">{ph}</p>
                        </div>
                      </div>
                    </div>

                    <div className="bg-blue-50 p-4 rounded-lg">
                      <h4 className="font-medium text-blue-800 mb-2">{t('crop_recommendation.climate_conditions')}</h4>
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
                        <div className="flex items-center">
                          <Thermometer className="h-4 w-4 text-red-500 mr-2" />
                          <div>
                            <p className="text-blue-600">Temperature</p>
                            <p className="font-medium">{temperature}°C</p>
                          </div>
                        </div>
                        <div className="flex items-center">
                          <Droplets className="h-4 w-4 text-blue-500 mr-2" />
                          <div>
                            <p className="text-blue-600">Humidity</p>
                            <p className="font-medium">{humidity}%</p>
                          </div>
                        </div>
                        <div className="flex items-center">
                          <Droplets className="h-4 w-4 text-cyan-500 mr-2" />
                          <div>
                            <p className="text-blue-600">Rainfall</p>
                            <p className="font-medium">{rainfall} mm</p>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="bg-green-50 p-4 rounded-lg">
                      <h4 className="font-medium text-green-800 mb-2">{t('crop_recommendation.farming_recommendations')}</h4>
                      <ul className="text-sm text-green-700 space-y-1">
                        {t('crop_recommendation.farming_tips', { returnObjects: true }).map((tip, index) => (
                          <li key={index}>• {tip}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </TabsContent>
              </Tabs>
            </CardContent>
          </>
        ) : (
          <div className="flex flex-col items-center justify-center h-full p-8 text-center">
            <div className="mb-4">
              <Sprout className="w-24 h-24 text-green-500 opacity-50" />
            </div>
            <h3 className="text-xl font-medium text-gray-700 mb-2">
              {t('crop_recommendation.no_recommendation')}
            </h3>
            <p className="text-gray-500 mb-6 max-w-md">
              {t('crop_recommendation.no_recommendation_desc')}
            </p>
            <div className="grid grid-cols-2 gap-4 text-left w-full max-w-md">
              <div className="flex items-start">
                <CheckCircle className="w-5 h-5 text-green-500 mr-2 mt-0.5" />
                <div>
                  <p className="text-sm font-medium">{t('crop_recommendation.ai_analysis')}</p>
                  <p className="text-xs text-gray-500">{t('crop_recommendation.ai_analysis_desc')}</p>
                </div>
              </div>
              <div className="flex items-start">
                <CheckCircle className="w-5 h-5 text-green-500 mr-2 mt-0.5" />
                <div>
                  <p className="text-sm font-medium">{t('crop_recommendation.personalized_results')}</p>
                  <p className="text-xs text-gray-500">{t('crop_recommendation.personalized_results_desc')}</p>
                </div>
              </div>
              <div className="flex items-start">
                <CheckCircle className="w-5 h-5 text-green-500 mr-2 mt-0.5" />
                <div>
                  <p className="text-sm font-medium">{t('crop_recommendation.detailed_insights')}</p>
                  <p className="text-xs text-gray-500">{t('crop_recommendation.detailed_insights_desc')}</p>
                </div>
              </div>
              <div className="flex items-start">
                <CheckCircle className="w-5 h-5 text-green-500 mr-2 mt-0.5" />
                <div>
                  <p className="text-sm font-medium">{t('crop_recommendation.expert_knowledge')}</p>
                  <p className="text-xs text-gray-500">{t('crop_recommendation.expert_knowledge_desc')}</p>
                </div>
              </div>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
};

export default CropRecommendation;
