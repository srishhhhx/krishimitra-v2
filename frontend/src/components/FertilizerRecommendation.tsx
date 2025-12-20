import React, { useState } from "react";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Slider } from "@/components/ui/slider";
import { CheckCircle, AlertCircle } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import { useTranslation } from "react-i18next";

interface SoilNutrient {
  name: string;
  value: number;
  unit: string;
  status: "Low" | "Medium" | "Optimal" | "High";
  color: string;
}

interface FertilizerRecommendation {
  name: string;
  formula: string;
  composition: string;
  purpose: string;
  bestFor: string;
  usageTip: string;
  avoid: string;
  applicationRate: string;
  timing: string;
  method: string;
  benefits: string[];
}

const FertilizerRecommendation: React.FC = () => {
  const { toast } = useToast();
  const { t } = useTranslation();
  const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";
  const [cropType, setCropType] = useState("");
  const [soilType, setSoilType] = useState("");
  const [growthStage, setGrowthStage] = useState("");
  const [soilPH, setSoilPH] = useState<number[]>([6.5]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [recommendations, setRecommendations] = useState<FertilizerRecommendation[]>([]);
  const [soilNutrients, setSoilNutrients] = useState<SoilNutrient[]>([]);
  // Additional numeric features required by backend model
  const [temperature, setTemperature] = useState<string>(""); // °C
  const [humidity, setHumidity] = useState<string>(""); // %
  const [moisture, setMoisture] = useState<string>(""); // % soil moisture
  const [nitrogen, setNitrogen] = useState<string>(""); // N
  const [phosphorous, setPhosphorous] = useState<string>(""); // P
  const [potassium, setPotassium] = useState<string>(""); // K

  const cropOptions = [
    "Maize",
    "Sugarcane",
    "Cotton",
    "Tobacco",
    "Paddy",
    "Barley",
    "Wheat",
    "Millets",
    "Oil seeds",
    "Pulses",
    "Ground Nuts",
  ];

  const soilOptions = [
    "Sandy",
    "Loamy",
    "Black",
    "Red",
    "Clayey",
  ];

  const growthStageOptions = [
    "Seedling", "Vegetative", "Flowering", "Fruiting", "Maturity"
  ];

  const mockSoilNutrients: SoilNutrient[] = [
    { 
      name: "Nitrogen (N)", 
      value: 25, 
      unit: "kg/ha", 
      status: "Low", 
      color: "bg-red-500" 
    },
    { 
      name: "Phosphorus (P)", 
      value: 15, 
      unit: "kg/ha", 
      status: "Medium", 
      color: "bg-yellow-500" 
    },
    { 
      name: "Potassium (K)", 
      value: 180, 
      unit: "kg/ha", 
      status: "Optimal", 
      color: "bg-green-500" 
    },
    { 
      name: "Organic Matter", 
      value: 1.2, 
      unit: "%", 
      status: "Low", 
      color: "bg-red-500" 
    },
  ];

  // Comprehensive fertilizer database with detailed information
  const fertilizerDatabase: { [key: string]: FertilizerRecommendation } = {
    "Urea": {
      name: "Urea",
      formula: "46-0-0",
      composition: "High nitrogen fertilizer (46% N)",
      purpose: "Promotes vegetative growth, greener leaves, and higher protein synthesis",
      bestFor: "Early crop stages (tillering in rice/wheat), leafy vegetables, and cereals",
      usageTip: "Apply in split doses to reduce nitrogen loss (volatilization)",
      avoid: "Overuse, as it can delay flowering and reduce yield quality",
      applicationRate: "100-150 kg/ha",
      timing: "Split application: 50% at 30 days, 50% at 60 days",
      method: "Side dressing followed by light irrigation",
      benefits: ["High nitrogen for leafy growth", "Cost-effective nitrogen source", "Quickly available to plants"]
    },
    "DAP": {
      name: "DAP (Di-Ammonium Phosphate)",
      formula: "18-46-0",
      composition: "18% Nitrogen, 46% Phosphorus",
      purpose: "Provides strong root development and supports early plant growth",
      bestFor: "Basal application before sowing in all major crops (grains, pulses, oilseeds)",
      usageTip: "Avoid mixing directly with urea; mix only at application time",
      avoid: "Excess use in alkaline soils (can cause phosphorus fixation)",
      applicationRate: "100-125 kg/ha",
      timing: "Apply as basal dose before sowing",
      method: "Band placement or broadcasting followed by incorporation",
      benefits: ["Strong root development", "Early plant establishment", "Improved nutrient uptake"]
    },
    "14-35-14": {
      name: "14-35-14 NPK Complex",
      formula: "14-35-14",
      composition: "14% Nitrogen, 35% Phosphorus, 14% Potassium",
      purpose: "Balanced fertilizer ideal for rooting, flowering, and fruit setting",
      bestFor: "Pulses, oilseeds, and fruit crops requiring balanced nutrient support",
      usageTip: "Use as a basal dose during sowing/transplantation",
      avoid: "Applying in nitrogen-rich soils without testing—can cause imbalance",
      applicationRate: "150-200 kg/ha",
      timing: "Apply at sowing/transplanting",
      method: "Band placement or broadcasting with incorporation",
      benefits: ["Balanced nutrition", "Enhanced flowering", "Better fruit setting"]
    },
    "28-28": {
      name: "28-28 NPK Complex",
      formula: "28-28-0",
      composition: "28% Nitrogen, 28% Phosphorus",
      purpose: "Boosts early vegetative and root development, especially for nutrient-demanding crops",
      bestFor: "Maize, sugarcane, and cereals in medium-fertility soils",
      usageTip: "Apply before irrigation for efficient nutrient absorption",
      avoid: "Repeated use without potassium supplements",
      applicationRate: "125-175 kg/ha",
      timing: "Apply at planting and early growth stages",
      method: "Band placement near root zone",
      benefits: ["Rapid early growth", "Strong root system", "Enhanced nutrient uptake"]
    },
    "17-17-17": {
      name: "17-17-17 NPK Complex",
      formula: "17-17-17",
      composition: "17% Nitrogen, 17% Phosphorus, 17% Potassium",
      purpose: "A general-purpose balanced fertilizer supporting all stages of crop growth",
      bestFor: "Vegetables, fruit crops, and multi-nutrient demanding cereals",
      usageTip: "Ideal as a top dressing in mid-growth stages",
      avoid: "Applying on high potassium soils — leads to nutrient lockout",
      applicationRate: "200-250 kg/ha",
      timing: "Apply at planting and as top dressing",
      method: "Broadcasting or side dressing",
      benefits: ["Complete nutrition", "Supports all growth stages", "Versatile application"]
    },
    "20-20": {
      name: "20-20 NPK Complex",
      formula: "20-20-0",
      composition: "20% Nitrogen, 20% Phosphorus",
      purpose: "Stimulates root development and chlorophyll formation",
      bestFor: "Oilseeds, pulses, and cereals during active growth",
      usageTip: "Combine with potash (MOP) if soil test shows low K levels",
      avoid: "Continuous use without organic matter—can reduce soil health",
      applicationRate: "150-200 kg/ha",
      timing: "Apply during active growth period",
      method: "Band placement or broadcasting",
      benefits: ["Enhanced chlorophyll", "Strong root development", "Improved photosynthesis"]
    },
    "10-26-26": {
      name: "10-26-26 NPK Complex",
      formula: "10-26-26",
      composition: "10% Nitrogen, 26% Phosphorus, 26% Potassium",
      purpose: "Encourages root establishment, flowering, and fruit formation",
      bestFor: "Fruit crops, flowering plants, and vegetables like tomato and chili",
      usageTip: "Apply at flowering/fruiting stage for best results",
      avoid: "Applying in excess during vegetative stage—it may slow leaf growth",
      applicationRate: "100-150 kg/ha",
      timing: "Apply at flowering and fruiting stages",
      method: "Side dressing around plant base",
      benefits: ["Enhanced flowering", "Better fruit quality", "Improved yield"]
    }
  };

  const generateRecommendations = async () => {
    if (!cropType || !soilType || !growthStage || !temperature || !humidity || !moisture || !nitrogen || !phosphorous || !potassium) {
      toast({ title: t('fertilizer_recommendation.missing_info'), description: t('fertilizer_recommendation.missing_info_desc'), variant: "destructive" });
      return;
    }
    // Build payload
    const payload = {
      Temperature: parseFloat(temperature),
      Humidity: parseFloat(humidity),
      Moisture: parseFloat(moisture),
      SoilType: Math.max(0, soilOptions.indexOf(soilType)),
      CropType: Math.max(0, cropOptions.indexOf(cropType)),
      Nitrogen: parseFloat(nitrogen),
      Phosphorous: parseFloat(phosphorous),
      Potassium: parseFloat(potassium),
    };

    setIsGenerating(true);
    try {
      const token = localStorage.getItem("access_token");
      const res = await fetch(`${API_BASE}/fertilizer_predict/predict`, {
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
      // Update UI: get detailed info from database or use default
      setSoilNutrients(mockSoilNutrients);
      const fertilizerName = data.recommended_fertilizer || "Unknown";
      const fertilizerInfo = fertilizerDatabase[fertilizerName] || {
        name: fertilizerName,
        formula: "—",
        composition: "Composition details not available",
        purpose: "General purpose fertilizer",
        bestFor: "Various crops as per agronomist guidance",
        usageTip: "Follow package instructions and soil test recommendations",
        avoid: "Overuse without proper soil testing",
        applicationRate: "As per package and agronomist guidance",
        timing: "Follow crop stage-specific schedule",
        method: "Broadcast/Banding per label",
        benefits: ["Backed by ML model", "Tailored to entered field conditions"]
      };
      setRecommendations([fertilizerInfo]);
      toast({ title: t('fertilizer_recommendation.recommendations_ready'), description: t('fertilizer_recommendation.recommendations_ready_desc') });
    } catch (e: any) {
      toast({ title: t('fertilizer_recommendation.error'), description: e?.message || t('fertilizer_recommendation.prediction_failed'), variant: "destructive" });
    }
    setIsGenerating(false);
  };

  const resetForm = () => {
    setCropType("");
    setSoilType("");
    setGrowthStage("");
    setSoilPH([6.5]);
    setTemperature("");
    setHumidity("");
    setMoisture("");
    setNitrogen("");
    setPhosphorous("");
    setPotassium("");
    setRecommendations([]);
    setSoilNutrients([]);
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <Card className="lg:col-span-1">
        <CardHeader>
          <CardTitle>{t('fertilizer_recommendation.title')}</CardTitle>
          <CardDescription>
            {t('fertilizer_recommendation.description')}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="crop-type">{t('fertilizer_recommendation.crop_type')}</Label>
              <Select value={cropType} onValueChange={setCropType}>
                <SelectTrigger id="crop-type">
                  <SelectValue placeholder={t('fertilizer_recommendation.select_crop')} />
                </SelectTrigger>
                <SelectContent>
                  {cropOptions.map((crop) => (
                    <SelectItem key={crop} value={crop}>{crop}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="soil-type">{t('fertilizer_recommendation.soil_type')}</Label>
              <Select value={soilType} onValueChange={setSoilType}>
                <SelectTrigger id="soil-type">
                  <SelectValue placeholder={t('fertilizer_recommendation.select_soil_type')} />
                </SelectTrigger>
                <SelectContent>
                  {soilOptions.map((soil) => (
                    <SelectItem key={soil} value={soil}>{soil}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="growth-stage">{t('fertilizer_recommendation.growth_stage')}</Label>
              <Select value={growthStage} onValueChange={setGrowthStage}>
                <SelectTrigger id="growth-stage">
                  <SelectValue placeholder={t('fertilizer_recommendation.select_growth_stage')} />
                </SelectTrigger>
                <SelectContent>
                  {growthStageOptions.map((stage) => (
                    <SelectItem key={stage} value={stage}>{stage}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="temp">{t('fertilizer_recommendation.temperature')}</Label>
                <Input id="temp" type="number" step="0.1" value={temperature} onChange={(e) => setTemperature(e.target.value)} placeholder="e.g., 28" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="humidity">{t('fertilizer_recommendation.humidity')}</Label>
                <Input id="humidity" type="number" step="0.1" value={humidity} onChange={(e) => setHumidity(e.target.value)} placeholder="e.g., 65" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="moisture">{t('fertilizer_recommendation.soil_moisture')}</Label>
                <Input id="moisture" type="number" step="0.1" value={moisture} onChange={(e) => setMoisture(e.target.value)} placeholder="e.g., 40" />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="n">{t('fertilizer_recommendation.nitrogen')}</Label>
                <Input id="n" type="number" step="0.1" value={nitrogen} onChange={(e) => setNitrogen(e.target.value)} placeholder="e.g., 90" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="p">{t('fertilizer_recommendation.phosphorous')}</Label>
                <Input id="p" type="number" step="0.1" value={phosphorous} onChange={(e) => setPhosphorous(e.target.value)} placeholder="e.g., 42" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="k">{t('fertilizer_recommendation.potassium')}</Label>
                <Input id="k" type="number" step="0.1" value={potassium} onChange={(e) => setPotassium(e.target.value)} placeholder="e.g., 37" />
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between">
                <Label htmlFor="soil-ph">{t('fertilizer_recommendation.soil_ph')}</Label>
                <span className="text-sm text-gray-500">{soilPH[0]}</span>
              </div>
              <Slider
                id="soil-ph"
                min={4.0}
                max={9.0}
                step={0.1}
                value={soilPH}
                onValueChange={setSoilPH}
              />
              <div className="flex justify-between text-xs text-gray-500">
                <span>{t('fertilizer_recommendation.acidic')}</span>
                <span>{t('fertilizer_recommendation.neutral')}</span>
                <span>{t('fertilizer_recommendation.alkaline')}</span>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="additional-info">{t('fertilizer_recommendation.additional_notes')}</Label>
              <Input
                id="additional-info"
                placeholder={t('fertilizer_recommendation.additional_notes_placeholder')}
              />
            </div>
          </form>
        </CardContent>
        <CardFooter className="flex justify-between">
          <Button variant="outline" onClick={resetForm} disabled={isGenerating}>
            {t('fertilizer_recommendation.reset')}
          </Button>
          <Button onClick={generateRecommendations} disabled={isGenerating}>
            {isGenerating ? t('fertilizer_recommendation.generating') : t('fertilizer_recommendation.generate_recommendations')}
          </Button>
        </CardFooter>
      </Card>

      <Card className="lg:col-span-2">
        {recommendations.length > 0 ? (
          <>
            <CardHeader>
              <CardTitle>{t('fertilizer_recommendation.fertilizer_recommendations')}</CardTitle>
              <CardDescription>
                {t('fertilizer_recommendation.based_on', { cropType, soilType, growthStage })}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="soil">
                <TabsList className="grid w-full grid-cols-2">
                  <TabsTrigger value="soil">{t('fertilizer_recommendation.soil_analysis')}</TabsTrigger>
                  <TabsTrigger value="fertilizer">{t('fertilizer_recommendation.fertilizer_plan')}</TabsTrigger>
                </TabsList>
                
                <TabsContent value="soil" className="pt-4">
                  <div className="space-y-6">
                    <div className="bg-blue-50 p-4 rounded-md flex items-start">
                      <AlertCircle className="w-5 h-5 text-blue-500 mr-2 mt-0.5" />
                      <div>
                        <p className="text-sm text-blue-700 font-medium">
                          {t('fertilizer_recommendation.soil_nutrient_status')}
                        </p>
                        <p className="text-xs text-blue-600 mt-1">
                          {t('fertilizer_recommendation.soil_nutrient_desc')}
                        </p>
                      </div>
                    </div>
                    
                    <div className="space-y-4">
                      {soilNutrients.map((nutrient, index) => (
                        <div key={index} className="space-y-2">
                          <div className="flex justify-between">
                            <span className="text-sm font-medium">{nutrient.name}</span>
                            <span className="text-sm">
                              {nutrient.value} {nutrient.unit} 
                              <span className={`ml-2 px-2 py-0.5 rounded-full text-xs text-white ${nutrient.color}`}>
                                {nutrient.status}
                              </span>
                            </span>
                          </div>
                          <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                            <div 
                              className={`h-full ${nutrient.color}`} 
                              style={{ width: `${Math.min(nutrient.status === "High" ? 100 : nutrient.status === "Optimal" ? 75 : nutrient.status === "Medium" ? 50 : 25, 100)}%` }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                    
                    <div className="bg-gray-50 p-4 rounded-md">
                      <p className="text-sm font-medium text-gray-700 mb-2">
                        Soil pH: {soilPH[0]} - {
                          soilPH[0] < 5.5 ? "Acidic" : 
                          soilPH[0] >= 5.5 && soilPH[0] <= 7.5 ? "Optimal" : "Alkaline"
                        }
                      </p>
                      <p className="text-xs text-gray-600">
                        {soilPH[0] < 5.5 ? 
                          "Consider applying agricultural lime to raise pH for better nutrient availability." : 
                          soilPH[0] > 7.5 ? 
                          "Consider applying sulfur or acidifying amendments to lower pH for better nutrient availability." : 
                          "Current pH is optimal for most crops and allows for good nutrient availability."
                        }
                      </p>
                    </div>
                  </div>
                </TabsContent>
                
                <TabsContent value="fertilizer" className="pt-4">
                  <div className="space-y-6">
                    {recommendations.map((rec, index) => (
                      <div key={index} className="border rounded-md p-4">
                        <div className="mb-6">
                          <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 mb-4">
                            <div className="flex items-center justify-between">
                              <div>
                                <p className="text-sm text-slate-600 font-medium mb-1">Recommended Fertilizer</p>
                                <h2 className="text-xl font-semibold text-slate-800">
                                  {rec.name}
                                </h2>
                              </div>
                              <span className="bg-emerald-100 text-emerald-700 px-3 py-1 rounded-md text-sm font-medium">
                                {rec.formula}
                              </span>
                            </div>
                          </div>
                        </div>
                        
                        <div className="space-y-4">
                          <div className="bg-green-50 p-3 rounded-lg">
                            <h4 className="text-sm font-semibold text-green-800 mb-1">Composition</h4>
                            <p className="text-sm text-green-700">{rec.composition}</p>
                          </div>
                          
                          <div className="bg-blue-50 p-3 rounded-lg">
                            <h4 className="text-sm font-semibold text-blue-800 mb-1">Purpose</h4>
                            <p className="text-sm text-blue-700">{rec.purpose}</p>
                          </div>
                          
                          <div className="bg-purple-50 p-3 rounded-lg">
                            <h4 className="text-sm font-semibold text-purple-800 mb-1">Best For</h4>
                            <p className="text-sm text-purple-700">{rec.bestFor}</p>
                          </div>
                          
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            <div className="bg-amber-50 p-3 rounded-lg">
                              <h4 className="text-sm font-semibold text-amber-800 mb-1">Usage Tip</h4>
                              <p className="text-sm text-amber-700">{rec.usageTip}</p>
                            </div>
                            <div className="bg-red-50 p-3 rounded-lg">
                              <h4 className="text-sm font-semibold text-red-800 mb-1">Avoid</h4>
                              <p className="text-sm text-red-700">{rec.avoid}</p>
                            </div>
                          </div>
                          
                          <div className="border-t pt-4">
                            <h4 className="text-sm font-semibold text-gray-800 mb-3">Application Details</h4>
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                              <div className="space-y-1">
                                <p className="text-xs text-gray-500 font-medium">Application Rate</p>
                                <p className="text-sm text-gray-700">{rec.applicationRate}</p>
                              </div>
                              <div className="space-y-1">
                                <p className="text-xs text-gray-500 font-medium">Timing</p>
                                <p className="text-sm text-gray-700">{rec.timing}</p>
                              </div>
                              <div className="space-y-1">
                                <p className="text-xs text-gray-500 font-medium">Method</p>
                                <p className="text-sm text-gray-700">{rec.method}</p>
                              </div>
                            </div>
                          </div>
                          
                          <div className="border-t pt-4">
                            <h4 className="text-sm font-semibold text-gray-800 mb-2">Key Benefits</h4>
                            <ul className="space-y-2">
                              {rec.benefits.map((benefit, idx) => (
                                <li key={idx} className="flex items-start">
                                  <CheckCircle className="w-4 h-4 text-green-500 mr-2 mt-0.5 shrink-0" />
                                  <span className="text-sm text-gray-700">{benefit}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </TabsContent>
              </Tabs>
            </CardContent>
          </>
        ) : (
          <div className="flex flex-col items-center justify-center h-full p-8 text-center">
            <div className="mb-4">
              <img 
                src="https://img.icons8.com/cotton/100/soil--v1.png" 
                alt="Soil and fertilizer" 
                className="w-24 h-24 opacity-50" 
              />
            </div>
            <h3 className="text-xl font-medium text-gray-700 mb-2">
              No Recommendations Yet
            </h3>
            <p className="text-gray-500 mb-6 max-w-md">
              Fill out the crop and soil information form to receive personalized 
              fertilizer recommendations based on your specific conditions.
            </p>
            <div className="grid grid-cols-2 gap-4 text-left w-full max-w-md">
              <div className="flex items-start">
                <CheckCircle className="w-5 h-5 text-green-500 mr-2 mt-0.5" />
                <div>
                  <p className="text-sm font-medium">Optimized Nutrition</p>
                  <p className="text-xs text-gray-500">Tailored to your crop needs</p>
                </div>
              </div>
              <div className="flex items-start">
                <CheckCircle className="w-5 h-5 text-green-500 mr-2 mt-0.5" />
                <div>
                  <p className="text-sm font-medium">Economic Benefits</p>
                  <p className="text-xs text-gray-500">Reduce waste and costs</p>
                </div>
              </div>
              <div className="flex items-start">
                <CheckCircle className="w-5 h-5 text-green-500 mr-2 mt-0.5" />
                <div>
                  <p className="text-sm font-medium">Sustainable Practices</p>
                  <p className="text-xs text-gray-500">Environmentally friendly</p>
                </div>
              </div>
              <div className="flex items-start">
                <CheckCircle className="w-5 h-5 text-green-500 mr-2 mt-0.5" />
                <div>
                  <p className="text-sm font-medium">Higher Yields</p>
                  <p className="text-xs text-gray-500">Maximize crop production</p>
                </div>
              </div>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
};

export default FertilizerRecommendation;
