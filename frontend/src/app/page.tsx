export default function Home() {
  return (
    <main className="min-h-screen bg-gray-50 flex flex-col items-center justify-center p-8">
      <div className="text-center max-w-3xl">
        <h1 className="text-5xl font-extrabold text-gray-900 mb-4 tracking-tight">
          Satya<span className="text-blue-600">Tathya</span>
        </h1>
        <p className="text-xl text-gray-600 mb-8">
          The Multimodal Fact-Checking Engine for Nepali Social Media
        </p>
        
        <div className="bg-white p-6 rounded-xl shadow-lg w-full">
          <form className="flex flex-col gap-4">
            <input 
              type="text" 
              placeholder="Paste a TikTok or Video URL here..." 
              className="w-full p-4 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-lg"
            />
            <button 
              type="submit" 
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-4 px-6 rounded-lg transition-colors text-lg"
            >
              Analyze Truth
            </button>
          </form>
        </div>
      </div>
    </main>
  );
}
