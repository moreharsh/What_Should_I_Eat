import React, { useState } from 'react';
import { Utensils, ArrowLeft, Clock, Users, Flame, ChevronRight, Play, CheckCircle2, Sparkles } from 'lucide-react';

const CUISINES = ['Indian', 'Mexican', 'Italian', 'Japanese', 'Mediterranean', 'Thai'];
const DIETARY_OPTIONS = ['Vegetarian', 'Vegan', 'Gluten-Free', 'Pescatarian', 'Dairy-Free'];

export default Object.assign(function App() {
  // 🚀 FIXED: Standardized view management states
  const [currentView, setCurrentView] = useState("cuisines"); // "cuisines" | "dashboard" | "menu_options" | "recipe"
  const [selectedCuisine, setSelectedCuisine] = useState('');
  const [selectedDiet, setSelectedDiet] = useState([]);
  const [triedFavorites, setTriedFavorites] = useState([]);
  
  // API Return Cache States
  const [menuOptions, setMenuOptions] = useState([]);
  const [selectedDish, setSelectedDish] = useState('');
  const [recipeDetails, setRecipeDetails] = useState(null);
  const [mediaLinks, setMediaLinks] = useState(null);
  
  // UI UX Polish States
  const [loading, setLoading] = useState(false);

  const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  const toggleDietary = (diet) => {
    setSelectedDiet(prev => 
      prev.includes(diet) ? prev.filter(d => d !== diet) : [...prev, diet]
    );
  };

  const refreshDashboardHistory = async (cuisineName) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/menu-dashboard`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: "harsh_123", cuisine: cuisineName })
      });
      const data = await response.json();
      if (data.has_history) {
        setTriedFavorites(data.previously_tried);
      } else {
        setTriedFavorites([]);
      }
      return data.has_history;
    } catch (err) {
      console.error("Error refreshing dashboard state:", err);
      return false;
    }
  };

  // 🚀 NEW: Checks history state to choose whether to display the split dashboard
  const handleCuisineSelect = async (cuisine) => {
    setSelectedCuisine(cuisine);
    setLoading(true);
    const hasHistory = await refreshDashboardHistory(cuisine);
    setLoading(false);
    
    if (hasHistory) {
      setMenuOptions([]); 
      setCurrentView("dashboard");
    } else {
      await triggerAiMenuGeneration(cuisine);
    }
  };

  // 🚀 MODIFIED: The original Phase 1 loop is now explicitly bound to the Exploration Column
  const triggerAiMenuGeneration = async (cuisineName) => {
    setLoading(true);
    setCurrentView("menu_options");
    try {
      const response = await fetch(`${API_BASE_URL}/api/menu`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          cuisine: cuisineName, 
          dietary_restrictions: selectedDiet // 🚀 FIXED: Renamed key to match your Pydantic schema!
        })
      });
      const data = await response.json();
      setMenuOptions(data.menu_options);
    } catch (err) {
      console.error("Error fetching menu options:", err);
    } finally {
      setLoading(false);
    }
  };

  // Phase 2: Call Backend to trigger concurrent Chef + Media assembly nodes
  const fetchRecipe = async (dishName) => {
    setSelectedDish(dishName);
    setLoading(true);
    setCurrentView("recipe");
    try {
      const response = await fetch(`${API_BASE_URL}/api/recipe`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ selected_dish: dishName, dietary_preferences: selectedDiet, cuisine: selectedCuisine })
      });
      const data = await response.json();
      setRecipeDetails(data.recipe_details);
      setMediaLinks(data.media_links);
    } catch (err) {
      console.error("Error fetching recipe details:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Header Layout */}
      <header className="flex items-center gap-3 mb-10 pb-6 border-b border-slate-200">
        <Utensils className="h-8 w-8 text-indigo-600" />
        <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-indigo-600 to-violet-600 bg-clip-text text-transparent">
          What Should I Eat?
        </h1>
      </header>

      {/* VIEW 1: SELECT CUISINE & PREFERENCES */}
      {currentView === "cuisines" && (
        <div className="space-y-8 animate-fadeIn">
          <div>
            <h2 className="text-xl font-semibold mb-3">Any dietary restrictions?</h2>
            <div className="flex gap-3">
              {DIETARY_OPTIONS.map(diet => (
                <button
                  key={diet}
                  onClick={() => toggleDietary(diet)}
                  className={`px-4 py-2 rounded-full border text-sm font-medium transition-all ${
                    selectedDiet.includes(diet)
                      ? 'bg-indigo-600 text-white border-indigo-600 shadow-sm'
                      : 'bg-white text-slate-700 border-slate-200 hover:border-slate-300'
                  }`}
                >
                  {diet}
                </button>
              ))}
            </div>
          </div>

          <div>
            <h2 className="text-xl font-semibold mb-4">What cuisine are you craving for dinner?</h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
              {CUISINES.map(cuisine => (
                <button
                  key={cuisine}
                  onClick={() => handleCuisineSelect(cuisine)} // 🚀 FIXED: Routed to historical router hook
                  className="p-6 text-left bg-white border border-slate-200 rounded-xl hover:border-indigo-500 hover:shadow-md transition-all group"
                >
                  <span className="text-lg font-bold group-hover:text-indigo-600 transition-colors block mb-1">
                    {cuisine}
                  </span>
                  <span className="text-xs text-slate-400 flex items-center gap-1">
                    Explore items <ChevronRight className="h-3 w-3" />
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 🚀 BRAND NEW VIEW: THE SPLIT-SCREEN MENU DASHBOARD */}
      {currentView === "dashboard" && (
        <div className="space-y-6 animate-fadeIn">
          <div className="flex items-center justify-between border-b border-slate-100 pb-4">
            <h2 className="text-2xl font-black text-slate-800 capitalize">🍳 Explore {selectedCuisine} Cuisine</h2>
            <button 
              onClick={() => setCurrentView("cuisines")}
              className="flex items-center gap-1 text-xs font-semibold px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-xl transition"
            >
              <ArrowLeft className="h-3 w-3" /> Back
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Left Column: Premium History Cards */}
            <div className="bg-slate-50 border border-slate-200/70 rounded-2xl p-5 space-y-4 shadow-xs">
              <div>
                <h3 className="text-sm font-black text-indigo-600 uppercase tracking-wider flex items-center gap-1.5">
                  <CheckCircle2 className="h-4 w-4 text-indigo-500" /> Tried & Trusted Favorites
                </h3>
                <p className="text-[11px] text-slate-400 mt-0.5">Loaded instantly from cloud storage memory caches</p>
              </div>
              
              <div className="space-y-3">
                {triedFavorites.map((dish, i) => (
                  <div
                    key={i}
                    onClick={() => fetchRecipe(dish.dish_name)} // Directly bypasses step 2 selection!
                    className="group bg-white p-4 rounded-xl border border-slate-100 shadow-2xs cursor-pointer hover:border-indigo-500 hover:shadow-sm transition-all flex justify-between items-start"
                  >
                    <div className="space-y-1 pr-4">
                      <div className="flex items-center gap-1.5">
                        <h4 className="text-sm font-bold text-slate-800 group-hover:text-indigo-600 transition-colors">{dish.dish_name}</h4>
                        <span className="text-[9px] px-1.5 py-0.5 bg-emerald-50 text-emerald-600 rounded font-bold">⚡ 10ms</span>
                      </div>
                      <p className="text-xs text-slate-500 line-clamp-2 leading-relaxed">{dish.teaser}</p>
                    </div>
                    <div className="text-right flex-shrink-0 space-y-1">
                      <div className="text-[10px] text-slate-400 font-medium">{dish.prep_time}</div>
                      <div className="text-[10px] px-1.5 py-0.5 bg-slate-100 text-slate-500 rounded font-bold capitalize">{dish.difficulty}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* 🚀 RIGHT COLUMN: Innovation & Action Target Block */}
            <div className="bg-slate-50 border border-slate-200/70 rounded-2xl p-5 flex flex-col shadow-xs min-h-[350px]">
              <div>
                <h3 className="text-sm font-black text-amber-600 uppercase tracking-wider flex items-center gap-1.5">
                  <Sparkles className="h-4 w-4 text-amber-500" /> Something Brand New
                </h3>
                <p className="text-[11px] text-slate-400 mt-0.5">Activate your multi-model AI agent mesh to discover flavors</p>
              </div>

              {/* CONDITIONAL RENDER: If no choices are generated yet, show the Magic Wand Button */}
              {menuOptions.length === 0 ? (
                <div className="flex-1 flex flex-col items-center justify-center text-center p-6 my-4 bg-white rounded-2xl border border-dashed border-slate-200">
                  <span className="text-3xl mb-2">🪄</span>
                  <h4 className="text-sm font-bold text-slate-700">Ready for a fresh creation?</h4>
                  <p className="text-xs text-slate-400 max-w-xs mt-1 mb-4">Click below to query your agent network for five customized culinary recommendations.</p>
                  <button
                    onClick={() => triggerAiMenuGeneration(selectedCuisine)}
                    className="px-5 py-2.5 text-xs font-bold text-white bg-amber-500 hover:bg-amber-600 rounded-xl shadow-sm transition transform active:scale-98"
                  >
                    {loading ? "Curation in progress..." : "Generate 5 Fresh Options"}
                  </button>
                </div>
              ) : (
                /* IF OPTIONS EXIST: Render them right here inside the dashboard panel! */
                <div className="mt-4 flex-1 space-y-2 overflow-y-auto">
                  <h4 className="text-[10px] font-black text-slate-400 uppercase tracking-wider mb-2">✨ Curated AI Recommendations:</h4>
                  {menuOptions.map((dish, idx) => (
                    <div 
                      key={idx}
                      onClick={() => fetchRecipe(dish.dish_name)}
                      className="p-3.5 bg-white border border-slate-100 rounded-xl hover:border-amber-500 hover:shadow-xs cursor-pointer transition-all flex justify-between items-center group"
                    >
                      <div className="space-y-0.5 max-w-[90%]">
                        <h4 className="text-xs font-bold text-slate-800 group-hover:text-amber-600 transition-colors">{dish.dish_name}</h4>
                        <p className="text-slate-500 text-[11px] line-clamp-1 leading-normal">{dish.teaser}</p>
                      </div>
                      <ChevronRight className="h-3 w-3 text-slate-300 group-hover:text-amber-500 transform group-hover:translate-x-0.5 transition-all flex-shrink-0" />
                    </div>
                  ))}
                  
                  {/* Optional Reset Button to clear and generate again */}
                  <button 
                    onClick={() => setMenuOptions([])}
                    className="w-full text-center text-[10px] font-bold text-slate-400 hover:text-slate-600 mt-2 transition"
                  >
                    Clear & Regenerate Options
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* VIEW 2: DISPLAY 5 AI RECIPE OPTIONS */}
      {currentView === "menu_options" && (
        <div className="space-y-6 animate-fadeIn">
          <button 
            onClick={() => setCurrentView(triedFavorites.length > 0 ? "dashboard" : "cuisines")} 
            className="flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-800 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" /> Back
          </button>
          
          <h2 className="text-2xl font-bold">5 Handpicked {selectedCuisine} Options</h2>

          {loading ? (
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-24 bg-slate-200 animate-pulse rounded-xl" />
              ))}
            </div>
          ) : (
            <div className="space-y-3">
              {menuOptions.map((dish, idx) => (
                <div 
                  key={idx}
                  onClick={() => fetchRecipe(dish.dish_name)}
                  className="p-5 bg-white border border-slate-200 rounded-xl hover:border-indigo-500 hover:shadow-sm cursor-pointer transition-all flex justify-between items-center group"
                >
                  <div className="space-y-1 max-w-[85%]">
                    <h3 className="text-lg font-bold group-hover:text-indigo-600 transition-colors">{dish.dish_name}</h3>
                    <p className="text-slate-600 text-sm leading-relaxed">{dish.teaser}</p>
                    <span className="inline-block bg-slate-100 text-slate-600 text-xs px-2 py-0.5 rounded font-medium">
                      Protein Base: {dish.primary_protein}
                    </span>
                  </div>
                  <ChevronRight className="h-5 w-5 text-slate-300 group-hover:text-indigo-500 transform group-hover:translate-x-1 transition-all" />
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* VIEW 3: FULL RECIPE DETAILS & RICH MEDIA ASSISTANT */}
      {currentView === "recipe" && (
        <div className="space-y-6 animate-fadeIn">
          <button 
            onClick={async () => {
              setLoading(true);
              // 🚀 FORCE RE-SYNC: Pull the item we just cooked straight from Redis Cloud
              await refreshDashboardHistory(selectedCuisine);
              setLoading(false);
              setCurrentView("dashboard");
            }}
            className="flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-800 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" /> Back to Menu Dashboard
          </button>

          {loading || !recipeDetails ? (
            <div className="space-y-4 animate-pulse">
              <div className="h-48 bg-slate-200 rounded-xl" />
              <div className="h-8 bg-slate-200 w-1/3 rounded" />
              <div className="h-24 bg-slate-200 rounded-xl" />
            </div>
          ) : (
            <div className="space-y-8">
              {/* Cover Card Banner */}
              <div 
                className="relative h-64 w-full bg-cover bg-center rounded-2xl shadow-inner flex items-end p-6 overflow-hidden border border-slate-200"
                style={{ backgroundImage: `url(${mediaLinks?.image_url})` }}
              >
                <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/40 to-transparent" />
                <h2 className="relative text-3xl font-black text-white">{recipeDetails.dish_name}</h2>
              </div>

              {/* Quick Spec Metadata Row */}
              <div className="grid grid-cols-3 gap-4 p-4 bg-white border border-slate-200 rounded-xl text-center shadow-sm">
                <div className="flex flex-col items-center gap-1 border-r border-slate-100">
                  <Clock className="h-5 w-5 text-indigo-500" />
                  <span className="text-xs text-slate-400 font-medium uppercase tracking-wider">Prep Time</span>
                  <span className="text-sm font-semibold">{recipeDetails.prep_time}</span>
                </div>
                <div className="flex flex-col items-center gap-1 border-r border-slate-100">
                  <Flame className="h-5 w-5 text-orange-500" />
                  <span className="text-xs text-slate-400 font-medium uppercase tracking-wider">Cook Time</span>
                  <span className="text-sm font-semibold">{recipeDetails.cook_time}</span>
                </div>
                <div className="flex flex-col items-center gap-1">
                  <Users className="h-5 w-5 text-emerald-500" />
                  <span className="text-xs text-slate-400 font-medium uppercase tracking-wider">Servings</span>
                  <span className="text-sm font-semibold">{recipeDetails.servings}</span>
                </div>
              </div>

              {/* Core Execution Columns */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                {/* Left Side: Ingredients */}
                <div className="md:col-span-1 bg-white border border-slate-200 p-6 rounded-2xl shadow-sm h-fit">
                  <h3 className="text-lg font-bold mb-4 pb-2 border-b border-slate-100">Ingredients</h3>
                  <ul className="space-y-3">
                    {recipeDetails.ingredients.map((item, index) => (
                      <li key={index} className="text-sm text-slate-600 leading-normal flex gap-2 items-start">
                        <span className="text-indigo-500 font-bold">•</span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Right Side: Step-by-Step Instructions */}
                <div className="md:col-span-2 space-y-6">
                  <div className="bg-white border border-slate-200 p-6 rounded-2xl shadow-sm">
                    <h3 className="text-lg font-bold mb-4 pb-2 border-b border-slate-100">Instructions</h3>
                    <ol className="space-y-4">
                      {recipeDetails.instructions.map((stepStr, index) => (
                        <li key={index} className="flex gap-4 items-start">
                          <span className="flex-shrink-0 h-6 w-6 bg-indigo-50 text-indigo-600 rounded-full flex items-center justify-center text-xs font-bold mt-0.5">
                            {index + 1}
                          </span>
                          <p className="text-sm text-slate-600 leading-relaxed">{stepStr}</p>
                        </li>
                      ))}
                    </ol>
                  </div>

                  {/* Chef Insider Pro-Tip */}
                  <div className="bg-amber-50/60 border border-amber-200/80 p-5 rounded-2xl">
                    <h4 className="text-amber-800 font-bold text-sm uppercase tracking-wider mb-1 flex items-center gap-1.5">
                      ⭐ Chef Pro-Tip
                    </h4>
                    <p className="text-amber-900 text-sm leading-relaxed">{recipeDetails.chef_pro_tip}</p>
                  </div>

                  {/* YouTube Interactive Player Frame */}
                  <div className="bg-white border border-slate-200 p-6 rounded-2xl shadow-sm">
                    <h3 className="text-lg font-bold mb-3 flex items-center gap-2">
                      <Play className="h-5 w-5 text-red-600 fill-red-600" /> Watch Recipe Tutorial
                    </h3>
                    <div className="aspect-video w-full rounded-xl overflow-hidden border border-slate-200 shadow-sm bg-slate-900">
                      <iframe 
                        className="w-full h-full"
                        src={mediaLinks?.youtube_embed_url} 
                        title="YouTube Recipe Video Player"
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                        allowFullScreen
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}, { displayName: 'App' });