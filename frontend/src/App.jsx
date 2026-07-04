import React, { useState } from 'react';
import { Utensils, ArrowLeft, Clock, Users, Flame, ChevronRight, Play } from 'lucide-react';

const CUISINES = ['Indian', 'Mexican', 'Italian', 'Japanese', 'Mediterranean'];
const DIETARY_OPTIONS = ['Vegetarian', 'Vegan', 'Gluten-Free'];

export default Object.assign(function App() {
  // Application Phase States
  const [step, setStep] = useState(1); // 1: Cuisine Choice, 2: Menu Options, 3: Recipe Details
  const [selectedCuisine, setSelectedCuisine] = useState('');
  const [selectedDiet, setSelectedDiet] = useState([]);
  
  // API Return Cache States
  const [menuOptions, setMenuOptions] = useState([]);
  const [selectedDish, setSelectedDish] = useState('');
  const [recipeDetails, setRecipeDetails] = useState(null);
  const [mediaLinks, setMediaLinks] = useState(null);
  
  // UI UX Polish States
  const [loading, setLoading] = useState(false);

  const toggleDietary = (diet) => {
    setSelectedDiet(prev => 
      prev.includes(diet) ? prev.filter(d => d !== diet) : [...prev, diet]
    );
  };

  // Phase 1: Call Backend to trigger Chef Agent Menu curation
  const fetchMenu = async (cuisine) => {
    setSelectedCuisine(cuisine);
    setLoading(true);
    setStep(2);
    try {
      const response = await fetch('http://localhost:8000/api/menu', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cuisine, dietary_preferences: selectedDiet })
      });
      const data = await response.json();
      setMenuOptions(data.menu_options);
    } catch (err) {
      console.error("Error fetching menu:", err);
    } finally {
      setLoading(false);
    }
  };

  // Phase 2: Call Backend to trigger concurrent Chef + Media assembly nodes
  const fetchRecipe = async (dishName) => {
    setSelectedDish(dishName);
    setLoading(true);
    setStep(3);
    try {
      const response = await fetch('http://localhost:8000/api/recipe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ selected_dish: dishName, dietary_preferences: selectedDiet })
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

      {/* STEP 1: SELECT CUISINE & PREFERENCES */}
      {step === 1 && (
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
                  onClick={() => fetchMenu(cuisine)}
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

      {/* STEP 2: DISPLAY 5 RECIPE OPTIONS */}
      {step === 2 && (
        <div className="space-y-6 animate-fadeIn">
          <button 
            onClick={() => setStep(1)} 
            className="flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-800 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" /> Change Cuisine
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

      {/* STEP 3: FULL RECIPE DETAILS & RICH MEDIA ASSISTANT */}
      {step === 3 && (
        <div className="space-y-6 animate-fadeIn">
          <button 
            onClick={() => setStep(2)} 
            className="flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-800 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" /> Back to Options
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