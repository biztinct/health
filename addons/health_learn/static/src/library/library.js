/** @odoo-module **/
import { Component, onMounted, onWillStart, onWillUpdateProps, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { RT } from "../engine/runtime";

const LABELS = {
    retryLoad: ["Retry", "Thử lại"], views: ["Learning views", "Chế độ học"],
    title: ["CareJiyo Learning", "Học cùng CareJiyo"],
    intro: ["Find a task, watch the walkthrough and follow the steps.", "Tìm công việc, xem video và làm theo từng bước."],
    search: ["Search tasks", "Tìm hướng dẫn"], library: ["Task library", "Thư viện hướng dẫn"],
    paths: ["My learning paths", "Lộ trình học của tôi"], coach: ["Ask the coach", "Hỏi trợ lý"],
    all: ["All topics", "Tất cả chủ đề"], steps: ["Steps", "Các bước"], watch: ["Watch", "Xem video"],
    before: ["Before you begin", "Trước khi bắt đầu"], result: ["Check the result", "Kiểm tra kết quả"],
    trouble: ["If something is wrong", "Nếu có vấn đề"], related: ["Related tasks", "Hướng dẫn liên quan"],
    back: ["Back to topics", "Trở lại danh sách"], manual: ["Open user manual", "Mở hướng dẫn sử dụng"],
    read: ["I have reviewed this guide", "Tôi đã đọc hướng dẫn này"], reviewed: ["Reviewed", "Đã đọc"],
    watched: ["Video watched", "Đã xem video"], noVideo: ["Follow the written steps for this task.", "Làm theo hướng dẫn bằng văn bản cho công việc này."],
    empty: ["No matching topics. Try another task name.", "Không tìm thấy. Hãy thử tên công việc khác."],
    context: ["Help for this screen", "Hướng dẫn cho màn hình này"], showAll: ["Browse all my topics", "Xem tất cả hướng dẫn của tôi"],
    english: ["Instructions in English. Vietnamese video subtitles are available.", "Hướng dẫn bằng tiếng Anh. Video có phụ đề tiếng Việt."],
    ask: ["Ask", "Hỏi"], question: ["What would you like help with?", "Bạn cần trợ giúp việc gì?"],
    asking: ["Finding a guide…", "Đang tìm hướng dẫn…"], guided: ["Open guided practice", "Mở bài thực hành"],
    practice: ["Practise with your trainer using a synthetic client. Reviewing a guide or watching a video does not certify competence.", "Thực hành cùng người hướng dẫn với khách hàng giả lập. Việc đọc hướng dẫn hoặc xem video không chứng nhận năng lực."],
    quiz: ["Knowledge check", "Kiểm tra kiến thức"], submit: ["Check my answer", "Kiểm tra câu trả lời"],
    correct: ["Correct", "Đúng"], retry: ["Review the guidance and try again", "Đọc lại hướng dẫn và thử lại"],
    passed: ["Knowledge check passed", "Đã đạt kiểm tra kiến thức"],
    choose: ["Select an answer first.", "Hãy chọn một câu trả lời."],
    error: ["Unable to load learning. Please try again.", "Không tải được hướng dẫn. Vui lòng thử lại."],
    savedError: ["Your progress could not be saved. Please try again.", "Không lưu được tiến độ. Vui lòng thử lại."],
    role: ["Learning path", "Lộ trình học"], section: ["Topic area", "Nhóm chủ đề"],
    chapters: ["Jump to a step", "Chuyển đến một bước"], openGuide: ["Read the guide", "Đọc hướng dẫn"],
    caption: ["Choose English or Vietnamese subtitles in the video controls.", "Chọn phụ đề tiếng Anh hoặc tiếng Việt trong trình phát video."],
};
const SECTIONS = [null, ["Getting started and enquiries","Bắt đầu và liên hệ"], ["Bookings and operations","Lịch hẹn và vận hành"], ["Mobile visits","Chăm sóc trên di động"], ["Invoices and payments","Hóa đơn và thanh toán"], ["Users and administration","Người dùng và quản trị"], ["Worked examples","Ví dụ thực hành"]];
const normalise = (text) => text.toLocaleLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d").trim();
const ROLES = {owner:["Owner","Chủ cơ sở"],operations:["Operations Manager","Quản lý vận hành"],crm:["CRM","CRM"],clinical:["Nurse or doctor","Điều dưỡng hoặc bác sĩ"],finance:["Finance","Tài chính"]};

export class TaskPanel extends Component {
    static template = "health_learn.TaskPanel";
    static props = { compact: {type: Boolean, optional:true}, screen: {type:String, optional:true}, startKey:{type:String,optional:true}, lang:{type:String,optional:true} };
    setup() {
        this.orm=useService("orm"); this.action=useService("action"); this.notification=useService("notification");
        this.video=useRef("video"); this.lastSave=0; this.requestId=0;
        this.state=useState({ready:false,error:false,query:"",section:"",mode:"library",task:null,tab:"steps",data:{tasks:[],paths:{},quizzes:{},progress:{}},role:"",question:"",answer:null,busy:false,quizAnswer:-1,quizResult:null,all:false,lang:this.props.lang||RT.lang||((user.lang||"").startsWith("vi")?"vi":"en")});
        onWillStart(()=>this.load());
        onWillUpdateProps((next)=>{if(next.lang&&next.lang!==this.props.lang)this.state.lang=next.lang;if(next.screen!==this.props.screen){this.requestId++;this.state.busy=false;this.stopVideo();this.state.task=null;this.state.answer=null;this.state.all=false;this.state.query="";}});
        this.onLanguage=(ev)=>{if(["en","vi"].includes(ev.detail))this.state.lang=ev.detail;};
        onMounted(()=>window.addEventListener("carejiyo-learning-language",this.onLanguage));
        onWillUnmount(()=>{this.requestId++;this.stopVideo();window.removeEventListener("carejiyo-learning-language",this.onLanguage);});
    }
    toggleLang(){this.state.lang=this.state.lang==="en"?"vi":"en";RT.lang=this.state.lang;window.dispatchEvent(new CustomEvent("carejiyo-learning-language",{detail:this.state.lang}));try{const prefs=JSON.parse(localStorage.getItem("cjxLearnPrefs")||"{}");prefs.lang=this.state.lang;localStorage.setItem("cjxLearnPrefs",JSON.stringify(prefs));}catch{}}
    label(key){return (LABELS[key]||[key,key])[this.state.lang==="vi"?1:0];}
    sectionName(n){return SECTIONS[n]?.[this.state.lang==="vi"?1:0]||"";}
    roleName(r){return ROLES[r]?.[this.state.lang==="vi"?1:0]||r;}
    title(t){return this.state.lang==="vi"?t.title_vi||t.title:t.title;}
    async load(){try{this.state.data=await this.orm.call("learn.task","get_catalog",[]);this.state.role=this.state.data.paths.owner?"owner":Object.keys(this.state.data.paths)[0]||"";this.state.ready=true;this.state.error=false;if(this.props.startKey)this.select(this.props.startKey);}catch{this.state.error=true;}}
    get sections(){return SECTIONS.map((s,i)=>i).filter(i=>i&&this.state.data.tasks.some(t=>t.section===i));}
    get filtered(){let list=this.state.data.tasks;if(this.props.compact&&this.props.screen&&!this.state.all&&!this.state.query)list=list.filter(t=>t.screens.includes(this.props.screen));const q=normalise(this.state.query);return list.filter(t=>(!this.state.section||String(t.section)===this.state.section)&&(!q||normalise([t.title,t.title_vi,t.goal,...t.search_phrases].join(" ")).includes(q)));}
    get pathTasks(){return (this.state.data.paths[this.state.role]||[]).map(key=>this.state.data.tasks.find(t=>t.key===key)).filter(Boolean);}
    get practiceTask(){return this.state.data.practice?.[this.state.role];}
    get quiz(){return this.state.data.quizzes[this.state.role];}
    get pathReviewed(){return this.pathTasks.filter(t=>this.progress(t.key).reviewed).length;}
    progress(key){return this.state.data.progress[key]||{};}
    select(key,start){this.stopVideo();this.state.task=this.state.data.tasks.find(t=>t.key===key)||null;this.state.tab=typeof start==="number"?"watch":"steps";this.startAt=typeof start==="number"?start:null;}
    back(){this.stopVideo();this.state.task=null;}
    changeMode(mode){this.stopVideo();this.state.mode=mode;this.state.task=null;}
    changeTab(tab){this.stopVideo();this.state.tab=tab;}
    stopVideo(){if(this.video.el)this.video.el.pause();}
    media(kind){return '/carejiyo/learn/media/'+encodeURIComponent(this.state.task.key)+'/'+kind;}
    manual(key){return '/carejiyo/learn/manual'+(key?'?key='+encodeURIComponent(key):'');}
    format(n){return Math.floor(n/60)+':'+String(Math.floor(n%60)).padStart(2,'0');}
    metadata(){const v=this.video.el;if(!v)return;const p=this.startAt===null?this.progress(this.state.task.key).position||0:this.startAt;v.currentTime=Math.min(p,Math.max(0,v.duration-1));this.startAt=null;}
    seek(start){if(this.video.el){this.video.el.currentTime=start;this.video.el.scrollIntoView({block:"center",behavior:"smooth"});this.video.el.play().catch(()=>{});}}
    async save(event,position=0){const t=this.state.task;if(!t)return;try{await this.orm.call("learn.task","record",[t.key,event,position]);this.state.data.progress[t.key]={...this.progress(t.key),...(event==="position"?{position}:{[event]:true})};}catch{if(event!=="position")this.notification.add(this.label("savedError"),{type:"warning"});}}
    timeUpdate(){const now=Date.now();if(now-this.lastSave>10000&&this.video.el){this.lastSave=now;this.save("position",this.video.el.currentTime);}}
    ended(){this.save("watched");this.save("position",0);}
    async ask(){const q=this.state.question.trim();if(!q||this.state.busy)return;const req=++this.requestId;this.state.busy=true;try{const answer=await this.orm.call("learn.task","answer",[q,this.props.screen||null]);if(req===this.requestId)this.state.answer=answer;}catch{this.notification.add(this.label("error"),{type:"warning"});}finally{if(req===this.requestId)this.state.busy=false;}}
    async checkQuiz(){if(this.state.quizAnswer<0){this.notification.add(this.label("choose"),{type:"warning"});return;}try{const role=this.state.role;const result=await this.orm.call("learn.task","check_quiz",[role,this.state.quizAnswer]);if(this.state.role===role)this.state.quizResult=result;this.state.data.progress['quiz:'+role]={quiz_passed:result.correct};}catch{this.notification.add(this.label("savedError"),{type:"warning"});}}
    practice(){this.action.doAction("health_learn.action_learn_journey");}
}

export class LearningLibrary extends Component {
    static template="health_learn.LearningLibrary";
    static components={TaskPanel};
    static props=["*"];
    get startKey(){return this.props.action?.params?.task_key||"";}
}
registry.category("actions").add("carejiyo_learning_library",LearningLibrary);
