n=power(2,10);

index=ones(n,1);
results=ones(n,1);
for i=1:1:n
    input=[10;100;3;i];
    input=input-minp;
    input=input./(maxp-minp)*2-1;
    index(i)=i;
    result=sim(net,input);
    result=result+1;
    result=result./2.*(maxt-mint);
    result=result+mint;
    result=power(result,-8);
    results(i)=result;
end
plot(index,results);