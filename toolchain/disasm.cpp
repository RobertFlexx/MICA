// mica-dis: flat-image disassembler, C++23 and no external dependencies.
// SPDX-License-Identifier: MIT
#include <array>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
using U=std::uint64_t;
static std::string hex(U value){std::ostringstream o;o<<"0x"<<std::hex<<value;return o.str();}
static std::string x(int n){return "x"+std::to_string(n);}
static std::string v(int n){return "v"+std::to_string(n);}
static std::string mem(int base,std::int64_t off){std::string s="["+x(base);if(off>0)s+="+"+std::to_string(off);else if(off<0)s+=std::to_string(off);return s+"]";}
static std::int64_t sx(U n,int bits){U sign=U(1)<<(bits-1),mask=(U(1)<<bits)-1;return std::int64_t((n&mask)^sign)-std::int64_t(sign);}
static std::string target(U pc,int size,U rel,int bits){return hex(U(std::int64_t(pc)+size+2*sx(rel,bits)));}
static const std::array<const char*,23> rnames={"nop","mov","add","sub","and","or","xor","shl","shr","sar","slt","sltu","seq","jr","jalr","not","neg","mul","wfi","fence","ecall","eret","fence.i"};
static const std::array<const char*,8> mn={"ldw","stw","ldh","sth","ldb","stb","ldhu","ldbu"};
static const std::array<const char*,12> a3={"add3","sub3","and3","or3","xor3","shl3","shr3","sar3","slt3","sltu3","seq3","mul3"};
static const std::array<const char*,7> a3i={"add3i","and3i","or3i","xor3i","shl3i","shr3i","sar3i"};
static const std::array<const char*,6> branches={"beq","bne","blt","bge","bltu","bgeu"};
static const std::array<const char*,9> words={"addw3","subw3","shlw3","shrw3","sarw3","andw3","orw3","xorw3","mulw3"};
static const std::array<const char*,6> qmem={"ldq","stq","ldws","ldwu","ldbs","ldhs"};
static const std::array<const char*,8> flow={"ldpi.b","ldpi.h","ldpi.w","ldpi.q","stpi.b","stpi.h","stpi.w","stpi.q"};
static const std::array<const char*,10> sys={"csrr","csrw","lr.w","sc.w","amoadd.w","amoswap.w","lr.q","sc.q","amoadd.q","amoswap.q"};
static const std::array<const char*,22> vec={"vadd","vsub","vmul","vand","vor","vxor","vshl","vshr","vsar","vmin","vmax","vcmpeq","vcmplt","vabs","vneg","vdot8","vld","vst","vziplo","vziphi","vunziplo","vunziphi"};
static std::string decode(U pc,U h,U p,int xlen){
    int cls=int(h>>14);
    if(cls==0){int op=int((h>>6)&255),d=int((h>>3)&7),s=int(h&7);
        if(op>=23&&op<=30)return std::string(flow[op-23])+" "+x(d)+",["+x(s)+"]";
        if(op>=int(rnames.size()))return ".half "+hex(h);
        std::string name=rnames[op];
        if(op==0||op>=18)return name;
        if(op==13||op==14||op==15||op==16)return name+" "+x(d);
        return name+" "+x(d)+","+x(s);
    }
    if(cls==1){int op=int((h>>11)&7),d=int((h>>8)&7),imm=int(h&255);
        if(op==7)return "b "+target(pc,2,h&2047,11);
        if(op==5||op==6)return std::string(op==5?"bz ":"bnz ")+x(d)+","+target(pc,2,h&255,8);
        if(op==0)return "li8 "+x(d)+","+std::to_string(sx(imm,8));
        if(op==1)return "addi "+x(d)+","+std::to_string(sx(imm,8));
        return std::string(op==2?"andi":op==3?"shli":"shri")+" "+x(d)+","+std::to_string(imm);
    }
    if(cls==2){int op=int((h>>11)&7),d=int((h>>8)&7),b=int((h>>5)&7),scale=(op<=1?4:(op==2||op==3||op==6?2:1));
        return std::string(mn[op])+" "+x(d)+","+mem(b,sx(h&31,5)*scale);
    }
    int maj=int((h>>10)&15);
    if(maj==0||maj==7){int op=int((p>>20)&63),d=int((p>>16)&15),a=int((p>>12)&15),b=int((p>>8)&15);
        if(maj==0&&op<int(a3.size()))return std::string(a3[op])+" "+x(d)+","+x(a)+","+x(b);
        if(maj==7&&op<int(words.size())&&xlen==64)return std::string(words[op])+" "+x(d)+","+x(a)+","+x(b);
    }
    if(maj==1){int op=int((p>>22)&15),d=int((p>>18)&15),a=int((p>>14)&15);
        if(op<int(a3i.size()))return std::string(a3i[op])+" "+x(d)+","+x(a)+","+(op==0?std::to_string(sx(p&16383,14)):hex(p&16383));
    }
    if(maj==2){int op=int((p>>20)&63),d=int((p>>16)&15);
        if(op<3)return std::string(op==0?"movhi":op==1?"movlo":"li16")+" "+x(d)+","+(op==2?std::to_string(sx(p&65535,16)):hex(p&65535));
    }
    if(maj==3){int op=int((p>>22)&15),a=int((p>>18)&15),b=int((p>>14)&15);
        if(op<int(branches.size()))return std::string(branches[op])+" "+x(a)+","+x(b)+","+target(pc,4,p&16383,14);
    }
    if(maj==4){int op=int((p>>24)&3);if(op<2)return std::string(op?"call ":"j ")+target(pc,4,p&0xffffff,24);}
    if(maj==8&&xlen==64){int op=int((p>>22)&15),d=int((p>>18)&15),b=int((p>>14)&15);
        if(op<int(qmem.size()))return std::string(qmem[op])+" "+x(d)+","+mem(b,sx(p&16383,14));
    }
    if(maj==9&&!(p>>24)){int d=int((p>>20)&15);return "dbnz "+x(d)+","+target(pc,4,p&0xfffff,20);}
    if(maj==10){int op=int((p>>22)&15),d=int((p>>18)&15),b=int((p>>14)&15);
        if(op<int(flow.size()))return std::string(flow[op])+" "+x(d)+",["+x(b)+"],"+std::to_string(sx(p&16383,14));
    }
    if(maj==5){int op=int((p>>20)&63),d=int((p>>16)&15),a=int((p>>12)&15),b=int((p>>8)&15);
        if(op<int(sys.size())){
            std::string n=sys[op];
            if(op==0)return n+" "+x(d)+","+hex(p&255);
            if(op==1)return n+" "+hex(p&255)+","+x(a);
            if(op==2||op==6)return n+" "+x(d)+",["+x(a)+"]";
            return n+" "+x(d)+","+x(b)+",["+x(a)+"]";
        }
    }
    if(maj==6){int op=int((p>>20)&63),d=int((p>>17)&7),a=int((p>>14)&7),b=int((p>>11)&7),ln=int((p>>9)&3),mode=int((p>>6)&7);
        if(op<int(vec.size())){
            if(op==16||op==17)return std::string(vec[op])+" "+v(d)+",["+x(a)+"]";
            std::string name=std::string(vec[op])+"."+(mode&1?"s":"u")+std::to_string(8<<ln);
            if(mode&2)name+=".sat";if(mode&4)name+=".rnd";
            return name+" "+v(d)+","+v(a)+(op==13||op==14?"":","+v(b));
        }
    }
    return ".unknown "+hex(h)+" "+hex(p);
}
int main(int argc,char**argv){
    try{
        std::string file;int xlen=32;
        for(int i=1;i<argc;i++){
            std::string a=argv[i];
            if(a=="--xlen"){
                if(++i==argc)throw std::runtime_error("--xlen expects 32 or 64");
                xlen=std::stoi(argv[i]);if(xlen!=32&&xlen!=64)throw std::runtime_error("invalid xlen");
            }else if(a=="--help"){std::cout<<"mica-dis [--xlen 32|64] program.bin\n";return 0;}
            else if(!file.empty()||a.starts_with('-'))throw std::runtime_error("unexpected option or extra file");
            else file=a;
        }
        if(file.empty())throw std::runtime_error("input binary required");
        std::ifstream f(file,std::ios::binary);if(!f)throw std::runtime_error("cannot open binary");
        std::vector<std::uint8_t> buf((std::istreambuf_iterator<char>(f)),{});
        for(size_t i=0;i<buf.size();){
            size_t left=buf.size()-i;
            if(left<2){std::cout<<hex(i)<<": .byte "<<hex(buf[i])<<"\n";break;}
            U h=U(buf[i])|(U(buf[i+1])<<8);int len=(h>>14)==3?4:2;
            if(left<size_t(len)){std::cout<<hex(i)<<": .half "<<hex(h)<<" ; truncated\n";break;}
            U p=len==4?((h&1023)<<16)|(U(buf[i+2])|(U(buf[i+3])<<8)):0;
            std::cout<<std::setw(10)<<std::left<<hex(i)<<" "<<std::setw(20)<<decode(i,h,p,xlen)<<" ; ";
            for(int j=0;j<len;j++)std::cout<<std::hex<<std::setfill('0')<<std::setw(2)<<unsigned(buf[i+size_t(j)]);
            std::cout<<std::dec<<std::setfill(' ')<<"\n";i+=size_t(len);
        }
        return 0;
    }catch(const std::exception&e){std::cerr<<"mica-dis: "<<e.what()<<"\n";return 1;}
}
