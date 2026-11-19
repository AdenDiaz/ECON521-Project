// Reproducible editable presentation. Run in Artifact Session, or call build()
// with an @oai/artifact-tool Presentation and the accompanying exhibit JSON.
export function build(p, d) {
  p.slides.keep([]);
  const C={ink:'#172C43',blue:'#246C91',teal:'#287B70',rust:'#AA523C',gray:'#506172',light:'#E7EDF1',white:'#FFFFFF'};
  const n=v=>Number(v).toLocaleString('en-US');
  const f=(v,k=2)=>Number(v).toFixed(k);
  const txt=(s,t,x,y,w,h,size=26,color=C.ink,bold=false)=>{
    const q=s.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
    q.text=t;q.text.style={fontSize:size,typeface:'Arial',color,bold,autoFit:'none',insets:0,verticalAlignment:'top',alignment:'left'};return q;
  };
  const slide=(title,source,tag='')=>{
    const s=p.slides.add({width:1280,height:720});s.background.fill=C.white;
    txt(s,title,56,38,1168,65,44,C.ink,true);
    if(tag)txt(s,tag,56,110,1168,32,20,C.teal,true);
    txt(s,source,56,657,1120,43,14,C.gray);
    txt(s,String(p.slides.items.length).padStart(2,'0'),1180,662,44,30,17,C.gray);
    s.speakerNotes.text=source;return s;
  };
  const table=(s,values,x,y,w,h,widths,size=23)=>{
    const q=s.tables.add({rows:values.length,columns:values[0].length,left:x,top:y,width:w,height:h,columnWidths:widths,values});
    q.borders.assign({fill:C.light,width:0.6,style:'solid'});
    q.cells.block({row:0,column:0,rowCount:values.length,columnCount:values[0].length}).assign({textStyle:{fontSize:size,typeface:'Arial',color:C.ink},fill:C.white,margins:{left:12,right:12,top:8,bottom:8},anchor:'center'});
    q.cells.block({row:0,column:0,rowCount:1,columnCount:values[0].length}).assign({fill:C.ink,textStyle:{fontSize:size,typeface:'Arial',bold:true,color:C.white}});
    return q;
  };
  const note=(s,t,y=580,h=60)=>txt(s,t,56,y,1168,h,23,C.gray);
  const axes={textStyle:{fontSize:18,typeface:'Arial',fill:C.gray},line:{fill:C.light,width:1},majorGridlines:{fill:C.light,width:1}};
  // Chart caches use 12 significant digits so editable Excel snapshots preserve
  // the literal values. Full estimator precision remains in the results CSVs.
  const portable=v=>typeof v==='number'?Number(v.toPrecision(12)):Array.isArray(v)?v.map(portable):v&&typeof v==='object'?Object.fromEntries(Object.entries(v).map(([k,x])=>[k,portable(x)])):v;
  const chart=(s,type,cfg)=>s.charts.add(type,portable({chartFill:C.white,plotAreaFill:C.white,chartLine:{fill:'none'},hasLegend:false,...cfg}));
  const hist=d.historical, main=d.main;

  // 1
  let s=slide('Fan attendance and home-team performance','Aden Diaz | ECON521 | Research progress | November 19, 2026');
  txt(s,'Does a larger crowd increase\nthe probability of a home win?',56,166,1168,154,52,C.ink,true);
  txt(s,'MLB and NBA evidence, with NFL as a calibration reference',56,346,1168,48,29,C.blue);
  txt(s,'Previous-game closeness → alternative IV search → weekend candidate',56,453,1168,50,26,C.gray);
  txt(s,'New in this update: preliminary OLS, reduced form and 2SLS',56,529,1168,48,29,C.teal,true);
  s.speakerNotes.text+='\nRepository main, commit 51c94a98731180e5be3415892c6846a0590f0250. Historical work stopped at first-stage relevance. Second stage is newly authorized and exploratory.';

  // 2
  s=slide('Research motivation and the seed paper','Sources: Ganz & Allsop (2024; online 2023), pp. 31, 35–36, 41, 44–45 (PDF pp. 2, 6–7, 12, 15–16); README.md');
  txt(s,'Crowds may affect effort, communication and officiating. Better teams also attract more fans, so attendance–win correlations need not be causal.',56,130,1168,82,27);
  table(s,[['','Ganz & Allsop','This project'],['Sample','2020–21 NBA; 808 games, 27 home teams','2001–2019 MLB and NBA'],['Attendance / outcome','Reported fans, including zero / home point margin','Positive recorded attendance / game home-win indicator'],['Instrument','COVID capacity limits announced in advance','Prior closeness, then exploratory weekend IV'],['Effect of interest','Extra fans in mostly empty arenas','Weekend-induced attendance changes in normal seasons']],56,234,1168,287,[184,492,492],22);
  note(s,'The seed controls for team, month, recent 10-game performance and local COVID. Its 1.74 points per 1,000 fans is not comparable to a win-probability coefficient.',548,80);

  // 3
  s=slide('Table 1. Data coverage and estimation samples','Sources: results/cleaning/data_coverage.csv; results/first_stage/selected_first_stage.csv; new results/second_stage_update/data_audit.json');
  const m=main.MLB,b=main.NBA;
  table(s,[['Measure','MLB','NBA','NFL'],['Cleaned source dates','1897–2025','1946–2025','2001–2019'],['Cleaned games','223,655','70,025','4,808'],['Historical first-stage N','46,300','24,264','Calibration only'],['New regular-season IV N',n(m.n),n(b.n),'Not estimated'],['New mean attendance',n(Math.round(m.attendance_mean)),n(Math.round(b.attendance_mean)),'—'],['New home-win share',f(100*m.home_win_mean,1)+'%',f(100*b.home_win_mean,1)+'%','—']],56,146,1168,354,[370,266,266,266],24);
  txt(s,'Broader scope: NBA, NFL and MLB. Completed estimation: MLB and NBA.',56,528,1168,38,27,C.teal,true);
  note(s,'New samples: calendar 2001–2019, regular season, valid positive attendance, decisive score and complete pregame controls. NFL supplies the 22.94% closeness anchor.',578,65);

  // 4
  s=slide('The original previous-game-closeness design','Sources: scripts/first_stage.py; results/first_stage/report.md; README.md','HISTORICAL DESIGN');
  txt(s,'Prior close game → fan interest → current attendance → home-team result',56,158,1168,65,32,C.blue,true);
  txt(s,'Separate instruments: did the current home team’s and away team’s immediately previous games end close?',56,252,1168,75,28);
  txt(s,'Why it seemed plausible',56,360,510,40,29,C.ink,true);
  txt(s,'Suspense may raise demand before the next game. Score-margin cutoffs have a simple interpretation across leagues.',56,415,510,138,27);
  txt(s,'Why validity was unresolved',660,360,564,40,29,C.ink,true);
  txt(s,'Closeness can reflect team quality, fatigue and momentum. Those channels may change the next result directly.',660,415,564,138,27);
  note(s,'NFL reference: |score margin| ≤ 3 in 1,103 / 4,808 games (22.94%). The same percentile maps to ≤ 1 MLB run and ≤ 5 NBA points; discrete shares differ.',579,65);

  // 5
  s=slide('Closeness produced weak first stages','Sources: results/first_stage/selected_first_stage.csv; common_percentile_grid.csv; report.md','TABLE 2 AND FIGURE 1 | HISTORICAL RESULTS');
  table(s,[['NFL-anchor specification','MLB','NBA'],['Prior-game cutoff','1 run','5 points'],['Achieved close share','28.25%','27.81%'],['Games','46,300','24,264'],['Classical joint partial F','3.47','1.72'],['Home-team joint Wald F','4.90','2.95']],56,166,544,328,[300,122,122],22);
  const curves=hist.curves;
  chart(s,'scatter',{position:{left:632,top:158,width:590,height:360},scatterOptions:{style:'line'},series:[
    {name:'MLB',xValues:curves.MLB.x,values:curves.MLB.y,line:{fill:C.blue,width:3},marker:{symbol:'none'}},
    {name:'NBA',xValues:curves.NBA.x,values:curves.NBA.y,line:{fill:C.teal,width:3},marker:{symbol:'none'}},
    {name:'F = 10 screen',xValues:[1,99],values:[10,10],line:{fill:C.rust,width:1.5,style:'dashed'},marker:{symbol:'none'}}],
    hasLegend:true,legend:{position:'bottom',textStyle:{fontSize:17,typeface:'Arial'}},xAxis:{...axes,title:'Closeness percentile (%)',min:0,max:100,majorUnit:25},yAxis:{...axes,title:'Classical joint partial F',min:0,max:11,majorUnit:2}});
  txt(s,'No tested cutoff had classical joint partial F > 10',56,536,1168,40,29,C.teal,true);
  note(s,'Figure 1 displays integer percentiles 1–99. Full transition grid also tested; extreme clustered Wald spikes come from nearly degenerate indicators. F > 10 is only a relevance screen.',586,58);

  // 6
  s=slide('Table 3. The exploratory alternative-IV search','Sources: results/instrument_candidates/expanded_candidate_report.md and underlying robustness CSVs; all_candidate_inventory.csv','HISTORICAL RESULTS | 772 CANDIDATE / SPECIFICATION ROWS');
  table(s,[['Candidate','MLB F','NBA F','Main qualification'],['Weekend (Sat/Sun)','131.79','64.93','Rest, travel, timing; no date FE'],['Home opener','193.25','110.66','Ceremonies and selected rosters'],['U.S. federal holiday','43.34','14.20','Selected schedules; no date FE'],['Mean prior 5 home gates','206.13','188.65','Persistent demand and team quality'],['Dome cold <13°C (12h)','14.86','—','MLB only; 10 team clusters; cutoff search'],['NBA rain ≥0.5mm (12h)','—','8.95','Travel; searched windows / thresholds'],['Metro conflict ±2h','5.59*','1.63*','Traffic / selection; weak clustered F']],56,154,1168,376,[330,130,130,578],21);
  txt(s,'Weekend leads the working shortlist; exclusion remains unproven',56,552,1168,45,28,C.teal,true);
  txt(s,'F = home-team/date Wald F, except * home-team-only baseline. Opener, prior gates and weather use date FE; weekend/holiday cannot. Models and samples differ.',56,607,1168,45,16,C.gray);

  // 7
  s=slide('Figure 2. Weekend relevance and robustness','Sources: historical team_season_fe_robustness.csv; new results/second_stage_update/model_results.csv','ADJUSTED FIRST STAGES | NEW MAIN AND SENSITIVITY MODELS');
  const fs=main.stage1Chart;
  chart(s,'bar',{position:{left:56,top:167,width:776,height:390},categories:fs.categories,series:[{name:'MLB',values:fs.MLB,fill:C.blue},{name:'NBA',values:fs.NBA,fill:C.teal}],barOptions:{direction:'column',grouping:'clustered',gapWidth:95},hasLegend:true,legend:{position:'bottom',textStyle:{fontSize:20,typeface:'Arial'}},xAxis:{...axes,majorGridlines:null,textStyle:{fontSize:19,typeface:'Arial'}},yAxis:{...axes,title:'Additional attendees (1,000)',min:0,max:7,majorUnit:1},dataLabels:{showValue:true,position:'outEnd',numberFormatCode:'0.00',textStyle:{fontSize:19,typeface:'Arial'}}});
  txt(s,'New main model',884,175,340,36,27,C.ink,true);
  txt(s,`MLB: +${n(Math.round(1000*m.fs.coef))} fans\nWald F = ${f(m.fs.wald_f,1)}\n\nNBA: +${n(Math.round(1000*b.fs.coef))} fans\nWald F = ${f(b.fs.wald_f,1)}`,884,234,340,270,27);
  note(s,'Weekend = Saturday/Sunday; Friday excluded. All bars are adjusted associations. Historical models include postseason and recorded hour; new models use regular-season samples. Date FE absorb weekend.',580,65);

  // 8
  s=slide('The preliminary second-stage specification','Sources: new scripts/second_stage_update/analysis_plan.md and weekend_iv.py; model_results.csv','NEW ANALYSIS | CHOICES FIXED BEFORE OUTCOME ESTIMATES WERE INSPECTED');
  txt(s,'Y = 1(home score > away score); A = attendance / 1,000; Z = Sat/Sun',56,155,1168,48,30,C.blue,true);
  txt(s,'A = πZ + Xγ + home-team×season FE + away-team×season FE + u',56,235,1168,50,28);
  txt(s,'Y = βA + Xδ + home-team×season FE + away-team×season FE + ε',56,295,1168,50,28);
  txt(s,'Same X in both stages',56,391,544,36,28,C.ink,true);
  txt(s,'Year×month effects; home/away rest, prior-game result and signed margin. Main omits unverified current start hour; adds it in sensitivity.',56,440,544,134,26);
  txt(s,'Inference and identifying variation',660,391,564,36,28,C.ink,true);
  txt(s,`Proper 2SLS structural-residual covariance, clustered by home team and game date. ${m.home_clusters} MLB / ${b.home_clusters} NBA team clusters. No date or weekday FE.`,660,440,564,134,26);
  note(s,'OLS, first stage, reduced form and IV use identical observations and controls within each league. Sensitivities change time FE and omit MLB doubleheaders; no current-game outcome controls.',586,58);

  // 9
  s=slide('Table 4. Preliminary outcome-model results','Source: new results/second_stage_update/model_results.csv; main specification; 95% t intervals, home-team/date clustering','NEW ANALYSIS | CONDITIONAL ON THE IV ASSUMPTIONS');
  const cell=(r,scale=100)=>`${f(scale*r.coef,2)} [${f(scale*r.ci_low,2)}, ${f(scale*r.ci_high,2)}]`;
  table(s,[['Estimate [95% CI]','MLB','NBA'],['OLS: attendance → home win (pp / 1,000)',cell(m.ols),cell(b.ols)],['First stage: weekend → attendance (1,000)',cell(m.fs,1),cell(b.fs,1)],['Reduced form: weekend → home win (pp)',cell(m.rf),cell(b.rf)],['2SLS: attendance → home win (pp / 1,000)',cell(m.iv),cell(b.iv)],['N; team / date clusters',`${n(m.n)}; ${m.home_clusters} / ${n(m.date_clusters)}`,`${n(b.n)}; ${b.home_clusters} / ${n(b.date_clusters)}`],['First stage: classical F / clustered Wald F',`${f(m.fs.classical_f,1)} / ${f(m.fs.wald_f,1)}`,`${f(b.fs.classical_f,1)} / ${f(b.fs.wald_f,1)}`]],56,153,1168,392,[548,310,310],22);
  note(s,'pp = percentage points. A positive coefficient means a higher game-level home-win probability. These are linear probability models; intervals do not resolve exclusion or scheduling selection.',575,69);

  // 10
  s=slide('Figure 3. Preliminary IV estimates','Source: new results/second_stage_update/model_results.csv and anderson_rubin.json; 95% intervals','NEW ANALYSIS | HOME-WIN PROBABILITY CHANGE PER 1,000 FANS');
  const est=main.forest;
  chart(s,'scatter',{position:{left:56,top:157,width:790,height:412},scatterOptions:{style:'lineWithMarkers'},series:est.series,
    xAxis:{...axes,title:'Percentage points per 1,000 attendees',min:est.min,max:est.max,majorUnit:est.step},yAxis:{...axes,min:0,max:5,visible:false,majorGridlines:null},hasLegend:false});
  txt(s,'OLS',884,174,340,35,25,C.gray,true);
  txt(s,`MLB ${cell(m.ols)}\nNBA ${cell(b.ols)}`,884,214,340,83,22);
  txt(s,'IV: main / week FE',884,328,340,35,25,C.ink,true);
  txt(s,main.ivSummary,884,370,340,145,24);
  note(s,main.arSummary,581,65);

  // 11
  s=slide('Weekend validity remains the central limitation','Sources: expanded_candidate_report.md; new data_audit.json and analysis_plan.md; research update report');
  txt(s,'Weekend changes more than fan availability',56,148,1168,44,32,C.rust,true);
  txt(s,'Rest and travel',56,233,330,39,28,C.ink,true);
  txt(s,'Days off do not fully measure fatigue, distance or time-zone changes.',56,288,330,126,27);
  txt(s,'Game timing',455,233,330,39,28,C.ink,true);
  txt(s,'Adding recorded hour changes NBA IV from −1.09 to −0.41 pp; its pregame status is unverified.',455,288,330,126,27);
  txt(s,'Schedule selection',854,233,370,39,28,C.ink,true);
  txt(s,'Matchups and high-demand games may be assigned selectively.',854,288,370,126,27);
  txt(s,'Date FE would remove common daily shocks—and the instrument itself.',56,465,1168,46,29,C.blue,true);
  note(s,'Other limits: exploratory candidate/threshold search, about 30 home-team clusters, attendance measurement and sellouts, stored NBA date/time convention, and MLB gate attribution in doubleheaders.',554,91);

  // 12
  s=slide('Current conclusions and next steps','Repository snapshot: main @ 51c94a98731180e5be3415892c6846a0590f0250 | New extension dated November 19, 2026');
  txt(s,'Completed previously',56,152,348,40,30,C.ink,true);
  txt(s,'Cleaned MLB/NBA samples; weak closeness first stages; broad alternative-IV search.',56,217,348,160,28);
  txt(s,'New in this update',465,152,350,40,30,C.teal,true);
  txt(s,main.conclusion,465,217,350,226,28);
  txt(s,'Next priorities',874,152,350,40,30,C.ink,true);
  txt(s,'Audit rest, travel and timing balance; validate attendance and dates; strengthen the exclusion argument before causal claims.',874,217,350,226,28);
  txt(s,'Weekend is a useful working candidate. Its causal interpretation remains conditional.',56,511,1168,82,33,C.blue,true);
  txt(s,'NFL remains calibration only; a separate league design is planned.',56,608,1168,32,23,C.gray);
  return p;
}
