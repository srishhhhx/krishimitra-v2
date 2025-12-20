
import React, { useState } from "react";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Upload, ImagePlus, CheckCircle, Info, AlertCircle } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/use-toast";
import { useTranslation } from "react-i18next";

interface DetectionResult {
  class: string;
  crop: string;
  disease: string;
  is_healthy: boolean;
  confidence: number;
  confidence_percentage: number;
}

interface ApiResponse {
  success: boolean;
  prediction?: DetectionResult;
  error?: string;
}

// Treatment and prevention recommendations based on disease type
const diseaseInfo: Record<string, { description: string; treatment: string[]; prevention: string[] }> = {
  "Apple scab": {
    description: "Apple scab is a fungal disease that causes dark, scabby lesions on leaves and fruit, leading to reduced fruit quality and yield.",
    treatment: [
      "Apply fungicides like captan or myclobutanil during wet periods",
      "Remove fallen leaves and infected fruit",
      "Prune to improve air circulation",
      "Use organic treatments like neem oil or baking soda spray"
    ],
    prevention: [
      "Plant scab-resistant apple varieties",
      "Ensure good air circulation through proper pruning",
      "Clean up fallen leaves in autumn",
      "Avoid overhead watering"
    ]
  },
  "Black rot": {
    description: "Black rot causes dark, circular lesions on leaves and can severely damage fruit, making them inedible.",
    treatment: [
      "Apply copper-based fungicides",
      "Remove and destroy infected plant material",
      "Improve drainage around plants",
      "Use systemic fungicides for severe infections"
    ],
    prevention: [
      "Plant resistant varieties when available",
      "Ensure proper plant spacing",
      "Remove plant debris regularly",
      "Practice crop rotation"
    ]
  },
  "Cedar apple rust": {
    description: "Cedar apple rust is a fungal disease that requires both apple and cedar trees to complete its life cycle, causing yellow spots on leaves.",
    treatment: [
      "Apply preventive fungicides in early spring",
      "Remove nearby cedar trees if possible",
      "Use myclobutanil or propiconazole fungicides",
      "Improve air circulation around trees"
    ],
    prevention: [
      "Plant rust-resistant apple varieties",
      "Remove cedar trees within 2 miles if feasible",
      "Apply preventive fungicide sprays",
      "Monitor weather conditions for infection periods"
    ]
  },
  "Powdery mildew": {
    description: "Powdery mildew appears as white, powdery spots on leaves and stems, thriving in warm, dry conditions with high humidity.",
    treatment: [
      "Apply sulfur-based or potassium bicarbonate fungicides",
      "Use neem oil or horticultural oils",
      "Remove heavily infected leaves",
      "Improve air circulation around plants"
    ],
    prevention: [
      "Plant in areas with good air circulation",
      "Avoid overhead watering",
      "Choose resistant varieties",
      "Space plants properly to reduce humidity"
    ]
  },
  "Cercospora leaf spot": {
    description: "Cercospora leaf spot (Gray Leaf Spot) causes circular gray spots with dark borders on corn leaves, reducing photosynthesis and yield.",
    treatment: [
      "Apply fungicides containing strobilurins or triazoles",
      "Remove infected plant debris",
      "Ensure adequate plant nutrition",
      "Use foliar fungicides during humid conditions"
    ],
    prevention: [
      "Plant resistant corn hybrids with GLS tolerance",
      "Practice 2-3 year crop rotation with soybeans or wheat",
      "Use no-till or reduced tillage to bury crop residue",
      "Maintain proper plant spacing (avoid overcrowding)",
      "Apply balanced fertilization - avoid excess nitrogen",
      "Plant at recommended seeding rates",
      "Choose fields with good drainage and air circulation",
      "Monitor weather conditions - disease favors warm, humid weather",
      "Remove volunteer corn plants that can harbor the pathogen"
    ]
  },
  "Common rust": {
    description: "Common rust appears as small, reddish-brown pustules on corn leaves, most severe in cool, humid conditions (60-77°F).",
    treatment: [
      "Apply fungicides if infection is severe early in season",
      "Remove infected lower leaves if practical",
      "Ensure proper plant nutrition with balanced fertilizer",
      "Monitor weather conditions for treatment timing"
    ],
    prevention: [
      "Plant rust-resistant corn varieties and hybrids",
      "Avoid planting in low-lying areas with poor air circulation",
      "Practice crop rotation with non-host crops (soybeans, wheat)",
      "Remove corn debris and volunteer plants after harvest",
      "Plant at proper seeding rates to avoid overcrowding",
      "Maintain adequate potassium levels in soil",
      "Choose well-drained fields when possible",
      "Monitor local disease forecasts and weather conditions",
      "Avoid late planting which increases rust pressure"
    ]
  },
  "Northern Leaf Blight": {
    description: "Northern leaf blight causes long, elliptical gray-green lesions on corn leaves, reducing photosynthetic area and grain yield significantly.",
    treatment: [
      "Apply fungicides containing strobilurins or triazoles",
      "Remove infected plant material when practical",
      "Ensure balanced fertilization with proper N-P-K ratios",
      "Time fungicide applications based on disease pressure and weather"
    ],
    prevention: [
      "Use resistant corn hybrids with Ht genes (Ht1, Ht2, Ht3)",
      "Practice minimum tillage to bury infected crop residue",
      "Rotate with non-host crops for 2-3 years (soybeans, wheat, alfalfa)",
      "Manage nitrogen fertilization - avoid excessive nitrogen",
      "Plant at recommended population densities",
      "Choose fields with good drainage and air circulation",
      "Remove volunteer corn and grassy weeds",
      "Monitor for early symptoms during tasseling stage",
      "Avoid continuous corn cropping in the same field",
      "Use certified, disease-free seed"
    ]
  },
  "Late blight": {
    description: "Late blight is a devastating disease caused by Phytophthora infestans, affecting potatoes and tomatoes, especially in cool, wet conditions.",
    treatment: [
      "Apply copper-based or systemic fungicides immediately",
      "Remove and destroy infected plants",
      "Improve drainage and air circulation",
      "Use protective fungicides preventively"
    ],
    prevention: [
      "Plant certified disease-free seed potatoes",
      "Ensure good drainage and air circulation",
      "Avoid overhead irrigation",
      "Monitor weather for blight-favorable conditions"
    ]
  },
  "Early blight": {
    description: "Early blight causes dark spots with concentric rings on tomato and potato leaves, progressing from lower to upper leaves.",
    treatment: [
      "Apply fungicides containing chlorothalonil or copper",
      "Remove affected lower leaves promptly",
      "Improve plant spacing and air circulation",
      "Water at soil level to keep foliage dry"
    ],
    prevention: [
      "Use certified disease-free seeds and transplants",
      "Practice crop rotation (3-4 years)",
      "Mulch to prevent soil splash",
      "Maintain proper plant nutrition"
    ]
  },
  "Bacterial spot": {
    description: "Bacterial spot causes small, dark spots on leaves and fruit, leading to defoliation and reduced fruit quality.",
    treatment: [
      "Apply copper-based bactericides",
      "Remove infected plant material",
      "Avoid overhead watering",
      "Use streptomycin where legally permitted"
    ],
    prevention: [
      "Use pathogen-free seeds and transplants",
      "Practice crop rotation",
      "Avoid working with wet plants",
      "Disinfect tools between plants"
    ]
  },
  "Leaf blight": {
    description: "Leaf blight causes browning and death of leaf tissue, often starting at leaf margins and progressing inward.",
    treatment: [
      "Apply appropriate fungicides based on pathogen",
      "Remove infected leaves and debris",
      "Improve air circulation",
      "Adjust watering practices"
    ],
    prevention: [
      "Choose resistant varieties",
      "Ensure proper plant spacing",
      "Avoid overhead watering",
      "Practice good sanitation"
    ]
  },
  "Septoria leaf spot": {
    description: "Septoria leaf spot causes small, circular spots with gray centers and dark borders on tomato leaves.",
    treatment: [
      "Apply fungicides containing chlorothalonil or copper",
      "Remove lower infected leaves",
      "Improve air circulation around plants",
      "Mulch to prevent soil splash"
    ],
    prevention: [
      "Use certified disease-free transplants",
      "Practice crop rotation",
      "Space plants properly for air circulation",
      "Water at soil level"
    ]
  },
  "Spider mites": {
    description: "Spider mites are tiny pests that cause stippling and yellowing of leaves, with fine webbing visible under severe infestations.",
    treatment: [
      "Apply miticides or insecticidal soaps",
      "Increase humidity around plants",
      "Use predatory mites as biological control",
      "Spray plants with water to dislodge mites"
    ],
    prevention: [
      "Maintain adequate humidity levels",
      "Avoid over-fertilizing with nitrogen",
      "Encourage beneficial insects",
      "Regular monitoring for early detection"
    ]
  },
  "Target Spot": {
    description: "Target spot causes circular lesions with concentric rings on tomato leaves and fruit, similar to early blight but with different patterns.",
    treatment: [
      "Apply fungicides containing azoxystrobin or chlorothalonil",
      "Remove infected plant debris",
      "Improve air circulation",
      "Rotate fungicide classes to prevent resistance"
    ],
    prevention: [
      "Use resistant varieties when available",
      "Practice crop rotation",
      "Ensure proper plant spacing",
      "Remove plant debris after harvest"
    ]
  },
  "Leaf Curl Virus": {
    description: "Tomato Yellow Leaf Curl Virus causes yellowing, curling, and stunting of tomato plants, transmitted by whiteflies.",
    treatment: [
      "Remove infected plants immediately",
      "Control whitefly populations with insecticides",
      "Use reflective mulches to deter whiteflies",
      "No cure exists - focus on prevention"
    ],
    prevention: [
      "Use virus-resistant tomato varieties",
      "Control whitefly populations",
      "Use physical barriers like row covers",
      "Remove weeds that harbor whiteflies"
    ]
  },
  "mosaic virus": {
    description: "Mosaic viruses cause mottled patterns of light and dark green on leaves, often with leaf distortion and stunting.",
    treatment: [
      "Remove infected plants to prevent spread",
      "Control aphid vectors with appropriate insecticides",
      "No chemical cure available",
      "Focus on preventing further spread"
    ],
    prevention: [
      "Use virus-free seeds and transplants",
      "Control aphid populations",
      "Remove weeds that can harbor viruses",
      "Practice good sanitation"
    ]
  },
  "Leaf Mold": {
    description: "Leaf mold causes yellowing of upper leaf surfaces with fuzzy growth on undersides, common in humid greenhouse conditions.",
    treatment: [
      "Improve ventilation and reduce humidity",
      "Apply fungicides containing chlorothalonil",
      "Remove infected leaves",
      "Increase air circulation"
    ],
    prevention: [
      "Maintain proper greenhouse ventilation",
      "Control humidity levels below 85%",
      "Space plants adequately",
      "Use resistant varieties"
    ]
  },
  "healthy": {
    description: "The plant appears to be healthy with no visible signs of disease or pest damage.",
    treatment: [
      "Continue regular care and monitoring",
      "Maintain proper watering schedule",
      "Ensure adequate nutrition",
      "Monitor for any changes in plant health"
    ],
    prevention: [
      "Regular inspection for early disease detection",
      "Maintain good garden hygiene",
      "Proper spacing and air circulation",
      "Balanced fertilization and watering"
    ]
  },
  // General corn/maize prevention measures
  "Gray leaf spot": {
    description: "Gray leaf spot is another name for Cercospora leaf spot, causing rectangular gray lesions on corn leaves.",
    treatment: [
      "Apply fungicides containing strobilurins or triazoles",
      "Remove infected plant debris",
      "Ensure adequate plant nutrition",
      "Use foliar fungicides during humid conditions"
    ],
    prevention: [
      "Plant resistant corn hybrids with GLS tolerance",
      "Practice 2-3 year crop rotation with soybeans or wheat",
      "Use no-till or reduced tillage to bury crop residue",
      "Maintain proper plant spacing (avoid overcrowding)",
      "Apply balanced fertilization - avoid excess nitrogen",
      "Plant at recommended seeding rates",
      "Choose fields with good drainage and air circulation",
      "Monitor weather conditions - disease favors warm, humid weather",
      "Remove volunteer corn plants that can harbor the pathogen"
    ]
  }
};

const DiseaseDetection: React.FC = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [result, setResult] = useState<DetectionResult | null>(null);
  const { toast } = useToast();
  const { t } = useTranslation();
  const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedFile(file);
      
      // Create image preview
      const reader = new FileReader();
      reader.onload = (event) => {
        setImagePreview(event.target?.result as string);
      };
      reader.readAsDataURL(file);
      
      // Reset previous results
      setResult(null);
    }
  };

  const handleAnalyze = async () => {
    if (!selectedFile) {
      toast({
        title: t('disease_detection.no_image'),
        description: t('disease_detection.no_image_desc'),
        variant: "destructive",
      });
      return;
    }

    setIsAnalyzing(true);
    
    try {
      const token = localStorage.getItem("access_token");
      if (!token) {
        throw new Error(t('disease_detection.auth_required'));
      }

      const formData = new FormData();
      formData.append("file", selectedFile);

      const response = await fetch(`${API_BASE}/crop_disease/detect-disease`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`,
        },
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      const data: ApiResponse = await response.json();
      
      if (data.success && data.prediction) {
        setResult(data.prediction);
        toast({
          title: t('disease_detection.analysis_complete'),
          description: `${t('disease_detection.detected')} ${data.prediction.crop} - ${data.prediction.disease}`,
        });
      } else {
        throw new Error(data.error || "Analysis failed");
      }
    } catch (error) {
      console.error("Disease detection error:", error);
      toast({
        title: t('disease_detection.analysis_failed'),
        description: error instanceof Error ? error.message : t('disease_detection.analysis_failed_desc'),
        variant: "destructive",
      });
    } finally {
      setIsAnalyzing(false);
    }
  };

  const resetForm = () => {
    setSelectedFile(null);
    setImagePreview(null);
    setResult(null);
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      <Card>
        <CardHeader>
          <CardTitle>{t('disease_detection.title')}</CardTitle>
          <CardDescription>
            {t('disease_detection.description')}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="grid w-full items-center gap-3">
              <Label htmlFor="plant-image" className="text-base font-semibold">
                {t('disease_detection.upload_label')}
              </Label>
              <div className="flex items-center gap-2">
                <Input
                  id="plant-image"
                  type="file"
                  accept="image/*"
                  onChange={handleFileChange}
                  className="hidden"
                />
                <div className="grid gap-2 w-full">
                  <Label
                    htmlFor="plant-image"
                    className="cursor-pointer flex items-center justify-center w-full border-2 border-dashed border-gray-300 rounded-lg h-48 hover:border-primary hover:bg-gray-50 transition-all duration-200 bg-gray-25"
                  >
                    {imagePreview ? (
                      <div className="w-full h-full relative p-2">
                        <img
                          src={imagePreview}
                          alt="Plant image preview"
                          className="w-full h-full object-contain rounded-md"
                        />
                        <div className="absolute top-2 right-2 bg-black bg-opacity-50 text-white px-2 py-1 rounded text-xs">
                          {t('disease_detection.preview')}
                        </div>
                      </div>
                    ) : (
                      <div className="flex flex-col items-center text-gray-500 p-6">
                        <ImagePlus className="w-12 h-12 mb-3 text-gray-400" />
                        <span className="text-lg font-medium mb-1">{t('disease_detection.click_upload')}</span>
                        <span className="text-sm text-gray-400">{t('disease_detection.drag_drop')}</span>
                        <div className="mt-3 text-xs text-gray-400">
                          {t('disease_detection.file_support')}
                        </div>
                      </div>
                    )}
                  </Label>
                  {selectedFile && (
                    <div className="flex items-center justify-between bg-gray-50 p-3 rounded-md">
                      <div className="flex items-center gap-2">
                        <CheckCircle className="w-4 h-4 text-green-500" />
                        <span className="text-sm font-medium text-gray-700">
                          {selectedFile.name}
                        </span>
                      </div>
                      <span className="text-xs text-gray-500">
                        {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="space-y-3">
              <Label className="text-sm font-semibold text-gray-700">{t('disease_detection.tips_title')}</Label>
              <div className="bg-blue-50 p-4 rounded-lg border-l-4 border-blue-400">
                <ul className="text-sm text-gray-700 space-y-2">
                  <li className="flex items-start gap-2">
                    <span className="text-blue-500 mt-0.5">•</span>
                    <span>{t('disease_detection.tips.lighting')}</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-blue-500 mt-0.5">•</span>
                    <span>{t('disease_detection.tips.focus')}</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-blue-500 mt-0.5">•</span>
                    <span>{t('disease_detection.tips.closeup')}</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-blue-500 mt-0.5">•</span>
                    <span>{t('disease_detection.tips.context')}</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-blue-500 mt-0.5">•</span>
                    <span>{t('disease_detection.tips.shadows')}</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-blue-500 mt-0.5">•</span>
                    <span>{t('disease_detection.tips.angles')}</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </CardContent>
        <CardFooter className="flex justify-between">
          <Button variant="outline" onClick={resetForm} disabled={isAnalyzing}>
            {t('disease_detection.reset')}
          </Button>
          <Button onClick={handleAnalyze} disabled={!selectedFile || isAnalyzing}>
            {isAnalyzing ? (
              <>{t('disease_detection.analyzing')}</>
            ) : (
              <>
                <Upload className="mr-2 h-4 w-4" /> {t('disease_detection.analyze')}
              </>
            )}
          </Button>
        </CardFooter>
      </Card>

      <Card className={result ? "" : "flex items-center justify-center"}>
        {result ? (
          <>
            <CardHeader>
              <CardTitle className="flex items-center">
                {result.is_healthy ? (
                  <CheckCircle className="w-6 h-6 text-green-500 mr-2" />
                ) : (
                  <AlertCircle className="w-6 h-6 text-red-500 mr-2" />
                )}
                <span className={result.is_healthy ? "text-green-600" : "text-red-600"}>
                  {result.crop} - {result.disease}
                </span>
              </CardTitle>
              <CardDescription>
                {diseaseInfo[result.disease]?.description || 
                 diseaseInfo[result.disease.toLowerCase()]?.description ||
                 `${result.disease} ${t('disease_detection.fallback_description')}`}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="treatment">
                <TabsList className="grid w-full grid-cols-2">
                  <TabsTrigger value="treatment">{t('disease_detection.treatment')}</TabsTrigger>
                  <TabsTrigger value="prevention">{t('disease_detection.prevention')}</TabsTrigger>
                </TabsList>
                <TabsContent value="treatment" className="pt-4">
                  <div className="space-y-4">
                    {!result.is_healthy && (
                      <div className="bg-amber-50 p-3 rounded-md">
                        <div className="flex items-start">
                          <Info className="w-5 h-5 text-amber-500 mr-2 mt-0.5" />
                          <p className="text-sm">
                            {t('disease_detection.treatment_note')}
                          </p>
                        </div>
                      </div>
                    )}
                    <ul className="space-y-2">
                      {(diseaseInfo[result.disease]?.treatment || 
                        diseaseInfo[result.disease.toLowerCase()]?.treatment ||
                        diseaseInfo["healthy"]?.treatment || 
                        [t('disease_detection.fallback_treatment')]).map((item, index) => (
                        <li key={index} className="flex items-start">
                          <CheckCircle className="w-5 h-5 text-green-500 mr-2 mt-0.5 shrink-0" />
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </TabsContent>
                <TabsContent value="prevention" className="pt-4">
                  <ul className="space-y-2">
                    {(diseaseInfo[result.disease]?.prevention || 
                      diseaseInfo[result.disease.toLowerCase()]?.prevention ||
                      diseaseInfo["healthy"]?.prevention || 
                      [t('disease_detection.fallback_prevention_1'), t('disease_detection.fallback_prevention_2')]).map((item, index) => (
                      <li key={index} className="flex items-start">
                        <CheckCircle className="w-5 h-5 text-blue-500 mr-2 mt-0.5 shrink-0" />
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </TabsContent>
              </Tabs>
            </CardContent>
          </>
        ) : (
          <div className="text-center p-6">
            <div className="rounded-full bg-gray-100 w-16 h-16 flex items-center justify-center mx-auto mb-4">
              <Upload className="h-8 w-8 text-gray-400" />
            </div>
            <h3 className="text-lg font-medium text-gray-700 mb-2">
              {t('disease_detection.no_results')}
            </h3>
            <p className="text-gray-500 text-sm">
              {t('disease_detection.no_results_desc')}
            </p>
          </div>
        )}
      </Card>
    </div>
  );
};

export default DiseaseDetection;
