// Saju × Zodiac 상세 분석 뷰 — saju-zodiac-test의 엔진/콘텐츠를 Lucky Path 오버레이로 이식
// window.ChartView.show(birthISO, birthTime) 로 연다.
(function () {
  /* ── 데이터 ── */
  const STEMS = [
    { han: "甲", name: "Jia", el: "Wood", en: "Yang Wood" },
    { han: "乙", name: "Yi", el: "Wood", en: "Yin Wood" },
    { han: "丙", name: "Bing", el: "Fire", en: "Yang Fire" },
    { han: "丁", name: "Ding", el: "Fire", en: "Yin Fire" },
    { han: "戊", name: "Wu", el: "Earth", en: "Yang Earth" },
    { han: "己", name: "Ji", el: "Earth", en: "Yin Earth" },
    { han: "庚", name: "Geng", el: "Metal", en: "Yang Metal" },
    { han: "辛", name: "Xin", el: "Metal", en: "Yin Metal" },
    { han: "壬", name: "Ren", el: "Water", en: "Yang Water" },
    { han: "癸", name: "Gui", el: "Water", en: "Yin Water" },
  ];
  const BRANCHES = [
    { han: "子", en: "Rat", el: "Water" }, { han: "丑", en: "Ox", el: "Earth" },
    { han: "寅", en: "Tiger", el: "Wood" }, { han: "卯", en: "Rabbit", el: "Wood" },
    { han: "辰", en: "Dragon", el: "Earth" }, { han: "巳", en: "Snake", el: "Fire" },
    { han: "午", en: "Horse", el: "Fire" }, { han: "未", en: "Goat", el: "Earth" },
    { han: "申", en: "Monkey", el: "Metal" }, { han: "酉", en: "Rooster", el: "Metal" },
    { han: "戌", en: "Dog", el: "Earth" }, { han: "亥", en: "Pig", el: "Water" },
  ];

  const DAY_MASTERS = {
    "甲": { img: "the Towering Tree", traits: ["Principled", "Ambitious", "Protective"],
      text: "Like a great tree that grows straight toward the sun, you carry an innate sense of direction and integrity. You prefer to lead rather than follow, and people naturally lean on you for shelter. Your challenge is flexibility — a tall tree that refuses to bend can break in a storm, so learn when to sway." },
    "乙": { img: "the Climbing Vine", traits: ["Adaptable", "Diplomatic", "Persistent"],
      text: "Like a vine or wildflower, you thrive through grace rather than force. You read rooms instantly, adapt to any environment, and quietly reach heights others achieve only through struggle. Beneath the softness is remarkable persistence — you always find a way around obstacles rather than through them." },
    "丙": { img: "the Blazing Sun", traits: ["Radiant", "Generous", "Expressive"],
      text: "You are the sun of any gathering — warm, open, and impossible to ignore. You give light without asking for repayment and inspire others simply by being fully yourself. Watch your tendency to burn too bright: not everyone can stand at noon, and even the sun must set to rise again." },
    "丁": { img: "the Candle Flame", traits: ["Insightful", "Devoted", "Refined"],
      text: "You are candlelight in the dark — subtle, precise, and deeply illuminating. Where Yang Fire floods a room, you focus warmth on the few things and people that matter most. You perceive what others miss, and your quiet devotion burns far longer than any bonfire." },
    "戊": { img: "the Great Mountain", traits: ["Steadfast", "Trustworthy", "Grounded"],
      text: "Like a mountain, you are the fixed point others navigate by. You keep promises, absorb pressure without complaint, and value substance over show. Change comes slowly to you — that is your strength and your lesson. Sometimes the mountain must let the river reshape its valley." },
    "己": { img: "the Fertile Field", traits: ["Nurturing", "Resourceful", "Patient"],
      text: "You are garden soil — modest in appearance, extraordinary in what you make possible. You cultivate people, projects, and ideas, turning raw seeds into harvests. Your quiet productivity is easily underestimated; remember to save some of that nourishment for yourself." },
    "庚": { img: "the Tempered Blade", traits: ["Decisive", "Just", "Resilient"],
      text: "Like raw ore forged into a sword, you were made for challenge. You cut through ambiguity, defend what is fair, and grow stronger with every trial by fire. Your directness is a gift wrapped in sharp edges — wield it with care around softer hearts." },
    "辛": { img: "the Polished Jewel", traits: ["Elegant", "Precise", "Discerning"],
      text: "You are refined metal — a jewel, a needle, a fine instrument. You value quality over quantity in everything: words, friendships, work. Your standards are exacting and your taste impeccable, but perfectionism can scratch even a diamond. Let a few flaws catch the light." },
    "壬": { img: "the Open Ocean", traits: ["Visionary", "Free-spirited", "Bold"],
      text: "You are the ocean — vast, restless, and impossible to contain. Big ideas and far horizons call to you, and you carry others along on your current. Your depths hold more than you show. Beware of drifting: even the sea obeys the moon, and you too need a rhythm to return to." },
    "癸": { img: "the Gentle Rain", traits: ["Intuitive", "Perceptive", "Subtle"],
      text: "You are rain and morning mist — soft, quiet, and quietly transformative. You seep into places force cannot reach, sensing emotions and truths before they are spoken. People underestimate you until they realize the whole landscape changed because of you." },
  };

  const ZODIACS = [
    { sym: "♑", name: "Capricorn", el: "Earth", dates: "Dec 22 – Jan 19", traits: ["Disciplined", "Strategic", "Enduring"],
      text: "Capricorn climbs. Ruled by Saturn, you treat life as a long ascent and rarely waste a step. Others see ambition; underneath is a dry wit and a fierce loyalty to the few who earn your trust." },
    { sym: "♒", name: "Aquarius", el: "Air", dates: "Jan 20 – Feb 18", traits: ["Original", "Humanitarian", "Independent"],
      text: "Aquarius lives ten years in the future. You question every default setting of society, collect unusual friends, and defend your independence like a homeland. Your detachment hides a genuine wish to make the world fairer." },
    { sym: "♓", name: "Pisces", el: "Water", dates: "Feb 19 – Mar 20", traits: ["Empathic", "Imaginative", "Fluid"],
      text: "Pisces feels everything — often other people's everything. Ruled by Neptune, you swim between dream and reality, turning emotion into art and intuition into uncanny timing. Boundaries are your lifelong homework." },
    { sym: "♈", name: "Aries", el: "Fire", dates: "Mar 21 – Apr 19", traits: ["Courageous", "Direct", "Pioneering"],
      text: "Aries goes first. Ruled by Mars, you'd rather make a bold mistake than a cautious nothing. Your anger burns out as fast as it flares, and your enthusiasm can drag an entire room into motion." },
    { sym: "♉", name: "Taurus", el: "Earth", dates: "Apr 20 – May 20", traits: ["Steadfast", "Sensual", "Patient"],
      text: "Taurus builds slowly and keeps what it builds. Ruled by Venus, you have a genius for comfort — good food, good textures, good company — and a stubbornness that is really just loyalty to your own judgment." },
    { sym: "♊", name: "Gemini", el: "Air", dates: "May 21 – Jun 21", traits: ["Curious", "Witty", "Versatile"],
      text: "Gemini is a conversation with the universe. Ruled by Mercury, you collect ideas, languages, and people, connecting dots nobody else noticed were on the same page. Boredom is your only real enemy." },
    { sym: "♋", name: "Cancer", el: "Water", dates: "Jun 22 – Jul 22", traits: ["Protective", "Intuitive", "Devoted"],
      text: "Cancer remembers. Ruled by the Moon, you feel in tides — fiercely protective of your people, deeply tuned to atmosphere, and armored in a shell that fools everyone but you. Home is not a place; it's your gravity." },
    { sym: "♌", name: "Leo", el: "Fire", dates: "Jul 23 – Aug 22", traits: ["Radiant", "Generous", "Proud"],
      text: "Leo warms the room and knows it. Ruled by the Sun, you lead with heart, celebrate loudly, and give more generously than anyone realizes. Your pride is real — but so is the loyalty behind it." },
    { sym: "♍", name: "Virgo", el: "Earth", dates: "Aug 23 – Sep 22", traits: ["Analytical", "Devoted", "Precise"],
      text: "Virgo perfects. Ruled by Mercury, you see the flaw, the fix, and the five steps to get there — usually before breakfast. Your care shows up as usefulness: quietly making everything and everyone around you work better." },
    { sym: "♎", name: "Libra", el: "Air", dates: "Sep 23 – Oct 23", traits: ["Harmonizing", "Fair", "Charming"],
      text: "Libra weighs. Ruled by Venus, you are the diplomat of the zodiac — allergic to ugliness and injustice alike. You see every side of every question, which makes you wise, and makes deciding lunch a small crisis." },
    { sym: "♏", name: "Scorpio", el: "Water", dates: "Oct 24 – Nov 21", traits: ["Intense", "Perceptive", "Transformative"],
      text: "Scorpio goes deep or not at all. Ruled by Pluto, you read hidden motives like subtitles and guard your own depths with elegant misdirection. What you love, you love totally — and you never do anything halfway." },
    { sym: "♐", name: "Sagittarius", el: "Fire", dates: "Nov 22 – Dec 21", traits: ["Adventurous", "Optimistic", "Philosophical"],
      text: "Sagittarius aims beyond the horizon. Ruled by Jupiter, you need movement, meaning, and the occasional reckless leap of faith. Your honesty can knock people over — but so can your laughter." },
  ];

  const ANIMAL_LINES = {
    Rat: "quick-witted and resourceful", Ox: "dependable and quietly powerful",
    Tiger: "brave and charismatic", Rabbit: "gentle and diplomatically brilliant",
    Dragon: "magnetic and larger than life", Snake: "wise and enigmatic",
    Horse: "free-spirited and energetic", Goat: "artistic and kind-hearted",
    Monkey: "clever and endlessly inventive", Rooster: "sharp-eyed and confident",
    Dog: "loyal and justice-driven", Pig: "sincere and generous of heart",
  };

  const COMBOS = {
    "Fire|Wood": { title: "The Kindled Visionary",
      text: "Wood feeds fire: your Saju nature is the fuel and your zodiac is the flame. Ideas that start as quiet convictions in you tend to ignite into bold public action. You grow fastest when you commit to one blaze at a time instead of scattering sparks — when aligned, you don't just chase dreams, you set them alight for everyone around you." },
    "Fire|Fire": { title: "The Double Flame",
      text: "Fire meets fire: East and West agree that you burn. Passion, charisma, and momentum come naturally — the world rarely wonders how you feel. Your work is rhythm, not restraint: build deliberate rest into your life the way a hearth needs tending, and your warmth becomes a lifelong gift instead of a series of brilliant flare-ups." },
    "Fire|Earth": { title: "The Warm Foundation",
      text: "Fire creates earth in the ancient cycle, and in you the bold zodiac flame rests on a deeply grounded Saju core. You look adventurous but decide carefully; you inspire others and then actually follow through. This is a rare combination of spark and stamina — the person who both starts the fire and builds the fireplace." },
    "Fire|Metal": { title: "The Forged Star",
      text: "Fire tempers metal: your fiery zodiac constantly tests your precise, principled Saju core — and makes it stronger. You hold high standards and the courage to defend them loudly. Friction is part of your design; every challenge you pass through leaves you sharper, brighter, and harder to bend." },
    "Fire|Water": { title: "The Storm of Passion",
      text: "Fire above, water below — you contain a genuine polarity. Outwardly bold and expressive, inwardly deep and intuitive, you can seem like two people who happen to share one destiny. When balanced, this is steam-engine power: emotion converted directly into momentum. Your art is honoring both natures instead of letting one extinguish the other." },
    "Earth|Wood": { title: "The Deep-Rooted Oak",
      text: "Wood takes root in earth: your steady zodiac ground gives your growing Saju nature somewhere to anchor. You combine patience with quiet ambition — growth that looks slow until everyone realizes you've become impossible to move. You build things (careers, families, reputations) that outlast trends." },
    "Earth|Fire": { title: "The Hearthkeeper",
      text: "Your inner Saju fire warms a practical, grounded zodiac shell. People come to you for both comfort and courage — soup and a pep talk. You dislike drama but radiate quiet intensity, and your steady warmth builds the kind of loyalty that louder flames never earn." },
    "Earth|Earth": { title: "The Unshakable One",
      text: "Earth doubled: both traditions crown you the reliable center of any world you inhabit. Promises kept, standards held, storms weathered — that's your signature. Your growth edge is spontaneity: the mountain doesn't have to move, but it can at least enjoy the weather changing." },
    "Earth|Metal": { title: "The Master Craftsman",
      text: "Earth bears metal: your grounded zodiac nature is the mine, and your refined Saju core is the ore within it. You turn patience into precision — the person whose work needs no excuses. Perfection is your instinct; remember that shipped and excellent beats flawless and imaginary." },
    "Earth|Water": { title: "The Hidden Spring",
      text: "Beneath your composed, practical zodiac surface runs deep Saju water — intuition, feeling, and quiet wisdom. You appear steady while sensing everything, which makes you a natural confidant and an underestimated strategist. Let the spring surface sometimes; your depths are worth showing." },
    "Air|Wood": { title: "The Wind-Blown Seed",
      text: "Air carries wood's seeds far from home: your curious, social zodiac nature spreads your growing Saju ambitions into places you'd never reach alone. You flourish through networks, conversations, and lucky introductions. Plant deliberately — your ideas take root wherever you let them land." },
    "Air|Fire": { title: "The Wildfire Mind",
      text: "Air feeds fire: your quick, connective zodiac mind is pure oxygen for your passionate Saju core. Ideas don't just occur to you — they combust. You're the person who talks a room into believing, then acts before doubt arrives. Aim the wind, and there is very little you can't ignite." },
    "Air|Earth": { title: "The Practical Dreamer",
      text: "Air above, earth below: you float through ideas and possibilities but land every decision on solid ground. This makes you rare — imaginative enough to see the future, practical enough to invoice it. Your best work happens when you translate between dreamers and builders, being fluent in both." },
    "Air|Metal": { title: "The Silver Tongue",
      text: "Air rings against metal like a struck bell: your social, articulate zodiac nature gives voice to your precise Saju core. Words are your instrument — persuading, refining, cutting through noise. You can win almost any argument; wisdom is knowing which ones deserve winning." },
    "Air|Water": { title: "The Mist Walker",
      text: "Air stirs water into mist: your intellectual zodiac and intuitive Saju blend thought and feeling until they're indistinguishable. You understand people with an accuracy that borders on unsettling. Your gift is atmosphere — you change the emotional weather of a room just by entering it." },
    "Water|Wood": { title: "The Nourished Grove",
      text: "Water feeds wood: your deep, feeling zodiac nature continuously nourishes your growing Saju core. Emotion becomes fuel for creation — you turn what you feel into what you build. Guard your source: you grow best beside people who refill your waters rather than drain them." },
    "Water|Fire": { title: "The Sacred Steam",
      text: "Water outside, fire within — an alchemical pairing. Your gentle, intuitive surface conceals a Saju core of real ambition and heat. People are perpetually surprised by your intensity; you feel deeply AND act boldly. The tension between the two is not a flaw. It's your engine." },
    "Water|Earth": { title: "The River's Keeper",
      text: "Water shapes earth over time, and in you a deeply feeling zodiac nature flows around a steady Saju core. You change people slowly and permanently — the friend whose influence is only visible in hindsight. Patience plus empathy is your quiet superpower." },
    "Water|Metal": { title: "The Moonlit Blade",
      text: "Metal enriches water in the ancient cycle: your intuitive zodiac depths carry a Saju core of clarity and precision. You feel your way to conclusions others need spreadsheets for — then defend them with steel. Elegant, perceptive, and far tougher than you look." },
    "Water|Water": { title: "The Bottomless Well",
      text: "Water doubled: both skies agree you are depth itself. Intuition, memory, and emotional intelligence run through everything you do — you don't read rooms, you absorb them. Your task is buoyancy: build shores and rituals that keep all that depth from becoming undertow." },
  };

  const ELEMENT_META = {
    Wood: { color: "#7ed49a", emoji: "🌿", colors: "Green & Teal", numbers: "3, 8" },
    Fire: { color: "#ff8a70", emoji: "🔥", colors: "Red & Coral", numbers: "2, 7" },
    Earth: { color: "#e0b56e", emoji: "⛰️", colors: "Amber & Terracotta", numbers: "5, 10" },
    Metal: { color: "#ccd2dc", emoji: "⚔️", colors: "White & Gold", numbers: "4, 9" },
    Water: { color: "#7cb5f2", emoji: "🌊", colors: "Navy & Black", numbers: "1, 6" },
  };
  const ELEMENT_ADVICE = {
    Wood: "growth, learning, and new beginnings — say yes to things that stretch you",
    Fire: "visibility, passion, and self-expression — let yourself be seen",
    Earth: "stability, routines, and trust — build foundations before towers",
    Metal: "clarity, structure, and finishing — cut what no longer serves you",
    Water: "rest, intuition, and wisdom — listen before you act",
  };

  /* ── 사주 엔진 (saju-zodiac-test와 동일, 기준일 2000-01-01=戊午 검증) ── */
  function julianDayNumber(y, m, d) {
    const a = Math.floor((14 - m) / 12);
    const yy = y + 4800 - a, mm = m + 12 * a - 3;
    return d + Math.floor((153 * mm + 2) / 5) + 365 * yy +
      Math.floor(yy / 4) - Math.floor(yy / 100) + Math.floor(yy / 400) - 32045;
  }
  function solarMonthIndex(m, d) {
    if (m === 1) return d >= 6 ? 11 : 10;
    const bounds = [[2, 4], [3, 6], [4, 5], [5, 6], [6, 6], [7, 7], [8, 8], [9, 8], [10, 8], [11, 7], [12, 7]];
    let idx = 11;
    for (let i = 0; i < bounds.length; i++) {
      const [bm, bd] = bounds[i];
      if (m > bm || (m === bm && d >= bd)) idx = i;
    }
    return idx;
  }
  function computeSaju(y, m, d, hour) {
    let solarYear = y;
    if (m === 1 || (m === 2 && d < 4)) solarYear = y - 1;
    const yStem = ((solarYear - 4) % 10 + 10) % 10;
    const yBranch = ((solarYear - 4) % 12 + 12) % 12;
    const mIdx = solarMonthIndex(m, d);
    const mBranch = (mIdx + 2) % 12;
    const mStem = ((yStem % 5) * 2 + 2 + mIdx) % 10;
    const dayIdx = ((julianDayNumber(y, m, d) + 49) % 60 + 60) % 60;
    const dStem = dayIdx % 10, dBranch = dayIdx % 12;
    let hStem = null, hBranch = null;
    if (hour !== null) {
      hBranch = Math.floor(((hour + 1) % 24) / 2);
      hStem = ((dStem % 5) * 2 + hBranch) % 10;
    }
    return { yStem, yBranch, mStem, mBranch, dStem, dBranch, hStem, hBranch };
  }
  function westernZodiac(m, d) {
    const cutoffs = [[1, 20], [2, 19], [3, 21], [4, 20], [5, 21], [6, 22],
      [7, 23], [8, 23], [9, 23], [10, 24], [11, 22], [12, 22]];
    const [, cd] = cutoffs[m - 1];
    return ZODIACS[(d >= cd ? m : m - 1) % 12];
  }
  function countElements(s) {
    const counts = { Wood: 0, Fire: 0, Earth: 0, Metal: 0, Water: 0 };
    const add = (el) => counts[el]++;
    add(STEMS[s.yStem].el); add(BRANCHES[s.yBranch].el);
    add(STEMS[s.mStem].el); add(BRANCHES[s.mBranch].el);
    add(STEMS[s.dStem].el); add(BRANCHES[s.dBranch].el);
    if (s.hStem !== null) { add(STEMS[s.hStem].el); add(BRANCHES[s.hBranch].el); }
    return counts;
  }

  /* ── 렌더 ── */
  function pillarCard(title, stemIdx, branchIdx, me) {
    if (stemIdx === null)
      return `<div class="pillar unknown"><div class="p-title">${title}</div>
        <div class="hanja">?<br>?</div><div class="p-en">Unknown<br>(no birth time)</div></div>`;
    const s = STEMS[stemIdx], b = BRANCHES[branchIdx];
    return `<div class="pillar${me ? " me" : ""}"><div class="p-title">${title}</div>
      <div class="hanja">${s.han}<br>${b.han}</div>
      <div class="p-en">${s.en}<br>over ${b.en}</div></div>`;
  }

  function buildHTML(y, m, d, hour) {
    const saju = computeSaju(y, m, d, hour);
    const zodiac = westernZodiac(m, d);
    const dayMaster = STEMS[saju.dStem];
    const dm = DAY_MASTERS[dayMaster.han];
    const animal = BRANCHES[saju.yBranch].en;
    const combo = COMBOS[`${zodiac.el}|${dayMaster.el}`];
    const counts = countElements(saju);
    const em = ELEMENT_META[dayMaster.el];

    const totalChars = saju.hStem !== null ? 8 : 6;
    const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
    const dominant = sorted[0];
    const missing = sorted.filter(([, c]) => c === 0).map(([e]) => e);

    const elPills = Object.entries(counts).map(([el, c]) =>
      `<div class="el-pill"><span class="dot" style="background:${ELEMENT_META[el].color}"></span>${el} <span class="cnt">× ${c}</span></div>`
    ).join("");

    let balanceNote = `Your chart is dominated by <b>${dominant[0]}</b> (${dominant[1]} of ${totalChars} characters), which colors your life with themes of ${ELEMENT_ADVICE[dominant[0]]}.`;
    balanceNote += missing.length
      ? ` You have no <b>${missing.join("</b> or <b>")}</b> in the visible chart — inviting more ${missing.map((e) => ELEMENT_ADVICE[e].split(" — ")[0]).join("; ")} into your life can restore balance.`
      : ` Remarkably, all five elements appear in your chart — a naturally well-rounded constitution.`;

    return `
      <div class="cv-hero">
        <div class="glyphs">${zodiac.sym} ✕ ${dayMaster.han}</div>
        <div class="eyebrow">Your Cosmic Archetype</div>
        <h2>${combo.title}</h2>
      </div>

      <div class="cv-sheet">
        <div class="sheet-top">
          <div class="thumb glyph-thumb">${zodiac.sym}<br>${dayMaster.han}</div>
          <div>
            <div class="cv-sheet-title">Natal Reading</div>
            <div class="cv-sheet-sub">${zodiac.el} (West) ✕ ${dayMaster.el} (East)</div>
          </div>
          <div class="badge">🔮</div>
        </div>
        <div class="stats">
          <div><label>Sun Sign</label><b>${zodiac.name}</b></div>
          <div><label>Day Master</label><b>${dayMaster.en}</b></div>
          <div><label>Year of the</label><b>${animal}</b></div>
        </div>
      </div>

      <div class="cvp">
        <h3>Your Four Pillars <span class="han">사주팔자</span></h3>
        <div class="tagline">The Eastern reading — your destiny chart</div>
        <div class="pillars">
          ${pillarCard("Hour · You", saju.hStem, saju.hBranch)}
          ${pillarCard("Day · Self", saju.dStem, saju.dBranch, true)}
          ${pillarCard("Month · Career", saju.mStem, saju.mBranch)}
          ${pillarCard("Year · Roots", saju.yStem, saju.yBranch)}
        </div>
        <div class="el-row">${elPills}</div>
        <p class="el-note">${balanceNote}</p>
      </div>

      <div class="cvp">
        <h3>Day Master: ${dayMaster.en} <span class="han">${dayMaster.han} ${dayMaster.name}</span></h3>
        <div class="tagline">The core of your Saju — who you are at the center</div>
        <div class="chips">${dm.traits.map((t) => `<span class="chip">${t}</span>`).join("")}</div>
        <p class="body">You are <b>${dm.img}</b>. ${dm.text}</p>
      </div>

      <div class="cvp">
        <h3>Sun Sign: ${zodiac.name} <span class="han">${zodiac.sym}</span></h3>
        <div class="tagline">The Western reading · ${zodiac.dates} · ${zodiac.el} sign</div>
        <div class="chips">${zodiac.traits.map((t) => `<span class="chip">${t}</span>`).join("")}</div>
        <p class="body">${zodiac.text}</p>
        <p class="body">And from the Eastern sky: as a <b>${animal}</b>-year native, you are ${ANIMAL_LINES[animal]}.</p>
      </div>

      <div class="cvp">
        <h3>The Synthesis: ${combo.title}</h3>
        <div class="tagline">${zodiac.el} (West) meets ${dayMaster.el} (East)</div>
        <p class="body">${combo.text}</p>
        <div class="lucky">
          <div class="lucky-item"><div class="l-label">Power Element</div><div class="l-val" style="color:${em.color}">${em.emoji} ${dayMaster.el}</div></div>
          <div class="lucky-item"><div class="l-label">Lucky Colors</div><div class="l-val">${em.colors}</div></div>
          <div class="lucky-item"><div class="l-label">Lucky Numbers</div><div class="l-val">${em.numbers}</div></div>
        </div>
      </div>

      <p class="cv-note">For entertainment purposes. Saju month & year boundaries use approximate solar-term dates.</p>`;
  }

  const overlay = () => document.getElementById("chart-overlay");

  window.ChartView = {
    show(birthISO, birthTime, city) {
      const [y, m, d] = birthISO.split("-").map(Number);
      const hour = birthTime ? Number(birthTime.split(":")[0]) : null;
      document.getElementById("chart-content").innerHTML = buildHTML(y, m, d, hour);
      document.getElementById("cv-birth").textContent =
        birthISO + (birthTime ? ` · ${birthTime}` : "") + (city ? ` · ${city}` : "");
      overlay().classList.add("open");
      overlay().scrollTop = 0;
    },
    hide() { overlay().classList.remove("open"); },
  };

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") window.ChartView.hide();
  });
})();
